"""Vue « Rapport client » — génère le compte-rendu hebdo prêt à envoyer."""

from __future__ import annotations

import streamlit as st

from core import gmail_draft, report, ui

ui.inject_theme()

df = ui.sidebar_data_source()
if df is None or df.empty:
    st.title("📧 Rapport client")
    st.info("👈 Importez d'abord vos fichiers dans la barre latérale.")
    st.stop()

flt = ui.sidebar_filters(df)
if flt is None:
    st.stop()
start, end, comparison = flt

current, prev_df, prev_range = ui.resolve_periods(df, start, end, comparison)
if current.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

period_label = f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
ui.pdf_export_button(current, prev_df, period_label, comparison)

ui.header_band(period_label, title="Rapport client — compte-rendu hebdo")

if comparison == "Aucune":
    st.info("💡 Active une **comparaison** (Période précédente / Année précédente) "
            "dans la sidebar pour inclure les variations WoW dans le compte-rendu.")
elif prev_df is None:
    st.warning("Pas de données sur la période de comparaison : le compte-rendu "
               "sera généré sans variations.")

st.caption("Compte-rendu généré automatiquement à partir de tes chiffres. "
           "Modifie-le librement, puis copie-le (icône en haut à droite du cadre) "
           "ou télécharge-le.")

email_text = report.build_email(current, prev_df, period_label, comparison)
edited = st.text_area("Compte-rendu", value=email_text, height=560,
                      key="report_text")

c1, c2 = st.columns(2)
with c1:
    st.download_button("⬇️ Télécharger en .txt", data=edited,
                       file_name=f"compte_rendu_sea_{start:%Y%m%d}.txt",
                       mime="text/plain", width="stretch")
with c2:
    st.caption("📄 Le **PDF complet** (tableaux + graphiques) se génère via le "
               "bouton « Générer le rapport PDF » dans la sidebar.")

# --- Brouillon Gmail ---
ui.section_band("Créer le brouillon Gmail")
if not gmail_draft.configured():
    st.info("✉️ **Activation Gmail** : ajoute tes identifiants OAuth dans les "
            "**Secrets Streamlit** (`[gmail]` client_id / client_secret / "
            "refresh_token). Voir **GMAIL_SETUP.md** dans le projet. "
            "Une fois fait, un bouton « Créer le brouillon » apparaîtra ici.")
else:
    g1, g2 = st.columns(2)
    to = g1.text_input("Destinataire (optionnel)", key="mail_to",
                       placeholder="client@exemple.com")
    subject = g2.text_input(
        "Objet", key="mail_subject",
        value=f"Point perf SEA — {st.session_state.get('client_name','')} "
              f"({period_label})".strip())
    if st.button("📧 Créer le brouillon dans Gmail", width="stretch"):
        try:
            gmail_draft.create_draft(subject, edited, to)
            st.success("✅ Brouillon créé dans Gmail — il est dans ton dossier "
                       "**Brouillons**, prêt à relire et envoyer.")
        except Exception as exc:
            st.error(f"Échec de la création du brouillon : {exc}")
