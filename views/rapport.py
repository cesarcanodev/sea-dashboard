"""Vue « Rapport client » — génère le compte-rendu hebdo prêt à envoyer."""

from __future__ import annotations

from urllib.parse import quote

import streamlit as st

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

gc1, gc2 = st.columns(2)
recipient = gc1.text_input(
    "Destinataire (salutation)", key="mail_greet",
    placeholder="Laurine   ·   Hortense et Agathe",
    help="Prénom(s) après « Hello ». Mets « et » ou une virgule pour passer "
         "automatiquement au vouvoiement (ex. « Hortense et Agathe »).")
signature = gc2.text_input("Signature", value="César", key="mail_sign")

st.caption("Compte-rendu rédigé dans ton ton. Modifie-le librement ; clique "
           "**« Régénérer »** après avoir changé la période, le destinataire ou "
           "la signature, puis copie-le (icône en haut à droite) ou télécharge-le.")

generated = report.build_email(current, prev_df, period_label, comparison,
                               recipient=recipient, signature=signature)
if st.button("🔄 Régénérer le compte-rendu") or "report_text" not in st.session_state:
    st.session_state["report_text"] = generated
edited = st.text_area("Compte-rendu", height=560, key="report_text")

# --- Envoi du compte-rendu (sans aucune connexion) ---
ui.section_band("Envoyer le compte-rendu")

e0, e1 = st.columns(2)
from_account = e0.text_input(
    "Ton compte Gmail (envoi)", key="mail_from",
    placeholder="prenom@agence.com",
    help="Ton adresse Gmail PRO. Le brouillon s'ouvrira sur CE compte "
         "(et non ton compte perso). Laisse vide pour le compte par défaut.")
to_email = e1.text_input("Email du destinataire", key="mail_to",
                         placeholder="laurine@exemple.com")
subject = st.text_input(
    "Objet", key="mail_subject",
    value=f"Point perf SEA — {st.session_state.get('client_name', '')} "
          f"({period_label})".strip())

# Liens « compose » pré-remplis : aucune connexion ni configuration requise.
# ``authuser`` route vers le bon compte Gmail connecté (pro vs perso).
su_q, body_q, to_q = quote(subject), quote(edited), quote(to_email)
auth = f"authuser={quote(from_account)}&" if from_account.strip() else ""
gmail_url = (f"https://mail.google.com/mail/?{auth}view=cm&fs=1&tf=1"
             f"&to={to_q}&su={su_q}&body={body_q}")
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

st.caption("💡 « Ouvrir dans Gmail » ne demande **aucune connexion** : renseigne "
           "ton **compte Gmail pro** ci-dessus pour que le brouillon s'ouvre sur "
           "le bon compte, relis, puis Envoie. Le **PDF complet** se génère via "
           "la sidebar.")

# --- Option avancée : brouillon Gmail automatique via OAuth ---
with st.expander("⚙️ Option avancée — brouillon Gmail automatique (connexion OAuth)"):
    if not gmail_draft.configured():
        st.info("Pour que l'app dépose elle-même le brouillon dans tes "
                "**Brouillons** Gmail, ajoute tes identifiants OAuth dans les "
                "**Secrets Streamlit** (`[gmail]`). Voir **GMAIL_SETUP.md**. "
                "Sinon, le bouton « Ouvrir dans Gmail » ci-dessus suffit.")
    elif st.button("📧 Créer le brouillon dans Gmail", width="stretch"):
        try:
            gmail_draft.create_draft(subject, edited, to_email)
            st.success("✅ Brouillon créé dans Gmail — dans ton dossier "
                       "**Brouillons**, prêt à relire et envoyer.")
        except Exception as exc:
            st.error(f"Échec de la création du brouillon : {exc}")
