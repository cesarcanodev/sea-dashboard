"""Vue « Rapport client » — génère le compte-rendu hebdo prêt à envoyer."""

from __future__ import annotations

from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from core import gmail_draft, report, ui

ui.inject_theme()

df = ui.sidebar_data_source()
if df is None or df.empty:
    st.title("📧 Rapport client")
    st.info("👈 Importez d'abord vos fichiers dans la barre latérale.")
    st.stop()

flt = ui.page_header(df, title="Rapport client — compte-rendu hebdo")
if flt is None:
    st.stop()
start, end, comparison = flt

current, prev_df, prev_range = ui.resolve_periods(df, start, end, comparison)
if current.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

period_label = f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
ui.pdf_export_button(current, prev_df, period_label, comparison)

if comparison == "Aucune":
    st.info("💡 Active une **comparaison** (Période précédente / Année précédente) "
            "dans la sidebar pour inclure les variations WoW dans le compte-rendu.")
elif prev_df is None:
    st.warning("Pas de données sur la période de comparaison : le compte-rendu "
               "sera généré sans variations.")

gc1, gc2, gc3 = st.columns(3)
recipient = gc1.text_input(
    "Destinataire (salutation)", key="mail_greet",
    placeholder="Laurine   ·   Hortense et Agathe",
    help="Prénom(s) après « Hello ». Mets « et » ou une virgule pour passer "
         "automatiquement au vouvoiement (ex. « Hortense et Agathe »).")
signature = gc2.text_input("Signature", value="César", key="mail_sign")
trend = gc3.text_input(
    "Objectif dépense/CA", key="mail_trend", placeholder="7 à 8 %",
    help="Optionnel : rappelle l'objectif de ratio dépense/CA en clôture. "
         "Ex. « 7 à 8 % » → « on reste bien dans le trend des 7 à 8 % ? ».")

st.caption("Compte-rendu rédigé dans ton ton. Modifie-le librement ; clique "
           "**« Régénérer »** après avoir changé la période, le destinataire ou "
           "la signature, puis copie-le (icône en haut à droite) ou télécharge-le.")

generated = report.build_email(current, prev_df, period_label, comparison,
                               recipient=recipient, signature=signature,
                               trend=trend)
if st.button("🔄 Régénérer le compte-rendu") or "report_text" not in st.session_state:
    st.session_state["report_text"] = generated
edited = st.text_area("Compte-rendu", height=560, key="report_text")

# --- Envoi du compte-rendu (sans aucune connexion) ---
ui.section_band("Envoyer le compte-rendu")

e0, e1 = st.columns([1, 2])
account_no = e0.number_input(
    "N° compte Gmail", min_value=0, max_value=9, value=0, step=1,
    key="mail_acct",
    help="Le numéro de TON compte Gmail pro dans l'URL. Ouvre ton Gmail pro et "
         "regarde l'adresse : mail.google.com/mail/u/1/… → mets 1. "
         "(0 = ton 1er compte connecté, souvent le perso.)")
to_email = e1.text_input("Email du destinataire", key="mail_to",
                         placeholder="laurine@exemple.com")
subject = st.text_input(
    "Objet", key="mail_subject",
    value=f"Point perf SEA — {st.session_state.get('client_name', '')} "
          f"({period_label})".strip())

# Lien « compose » pré-rempli. Le chemin /u/<n>/ cible un compte Gmail précis
# (méthode fiable, contrairement à authuser que Gmail ignore souvent).
su_q, body_q, to_q = quote(subject), quote(edited), quote(to_email)
gmail_url = (f"https://mail.google.com/mail/u/{int(account_no)}/"
             f"?view=cm&fs=1&tf=1&to={to_q}&su={su_q}&body={body_q}")
mailto_url = f"mailto:{to_q}?subject={su_q}&body={body_q}"

b1, b2, b3 = st.columns(3)
with b1:
    st.link_button("📧 Ouvrir dans Gmail", gmail_url, width="stretch",
                   help="Ouvre une fenêtre Gmail avec destinataire, objet et "
                        "corps déjà remplis — tu relis et tu envoies. Aucune "
                        "connexion à configurer.")
with b2:
    st.link_button("✉️ Ouvrir dans ma messagerie", mailto_url, width="stretch",
                   help="Ouvre ton logiciel de mail par défaut "
                        "(Outlook, Apple Mail…) avec le mail pré-rempli.")
with b3:
    st.download_button("⬇️ Télécharger .txt", data=edited,
                       file_name=f"compte_rendu_sea_{start:%Y%m%d}.txt",
                       mime="text/plain", width="stretch")

st.caption("💡 « Ouvrir dans Gmail » ne demande **aucune connexion** : mets le "
           "**n° de ton compte pro** (visible dans l'URL de ton Gmail, "
           "`…/mail/u/1/` → 1) pour que le mail s'ouvre sur le bon compte, relis, "
           "puis Envoie. Le **PDF complet** se génère via la sidebar.")

# --- Version mise en forme (tableaux bordés, total/en-têtes en gras, WoW
#     vert/rouge) à coller dans Gmail en conservant la mise en forme. ---
ui.section_band("Version mise en forme (à coller dans Gmail)")
email_html = report.build_email_html(current, prev_df, period_label, comparison,
                                     recipient=recipient, signature=signature,
                                     trend=trend)
_copy = f"""
<div style="font-family:Arial,Helvetica,sans-serif;">
  <button id="cpy" style="background:#384959;color:#fff;border:none;padding:10px 18px;
      border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;">
      📋 Copier le mail mis en forme</button>
  <span id="msg" style="margin-left:12px;color:#2E7D5B;font-size:13px;font-weight:600;"></span>
  <div id="mailbox" style="border:1px solid #E3EAF3;border-radius:10px;padding:16px;
      margin-top:12px;background:#fff;">{email_html}</div>
</div>
<script>
document.getElementById('cpy').addEventListener('click', async () => {{
  const box = document.getElementById('mailbox');
  try {{
    await navigator.clipboard.write([new ClipboardItem({{
      'text/html': new Blob([box.innerHTML], {{type:'text/html'}}),
      'text/plain': new Blob([box.innerText], {{type:'text/plain'}})
    }})]);
    document.getElementById('msg').textContent = '✅ Copié ! Colle dans Gmail (Cmd+V), la mise en forme est conservée.';
  }} catch (e) {{
    document.getElementById('msg').textContent = 'Copie auto indisponible — sélectionne le tableau ci-dessous puis Cmd+C.';
  }}
}});
</script>
"""
components.html(_copy, height=640, scrolling=True)
st.caption("Cette version reprend tes chiffres mis en forme. Les ajouts "
           "éditoriaux (contexte « ventes press », « soldes »…) se font après "
           "collage dans Gmail.")

# --- Option avancée : brouillon Gmail automatique via OAuth (mis en forme) ---
with st.expander("⚙️ Option avancée — brouillon Gmail automatique (connexion OAuth)"):
    if not gmail_draft.configured():
        st.info("Pour que l'app dépose elle-même le brouillon **mis en forme** "
                "dans tes **Brouillons** Gmail, ajoute tes identifiants OAuth dans "
                "les **Secrets Streamlit** (`[gmail]`). Voir **GMAIL_SETUP.md**. "
                "Sinon, le bouton « Copier le mail mis en forme » ci-dessus suffit.")
    elif st.button("📧 Créer le brouillon (mis en forme) dans Gmail",
                   width="stretch"):
        try:
            gmail_draft.create_draft(subject, edited, to_email, html=email_html)
            st.success("✅ Brouillon mis en forme créé dans Gmail — dans ton "
                       "dossier **Brouillons**, prêt à relire et envoyer.")
        except Exception as exc:
            st.error(f"Échec de la création du brouillon : {exc}")
