"""Vue « Analyse & Recommandations » — constats automatiques + actions."""

from __future__ import annotations

import streamlit as st

from core import analytics, ui

ui.inject_theme()

df = ui.sidebar_data_source()
if df is None or df.empty:
    st.title("🔍 Analyse & Recommandations")
    st.info("👈 Importez d'abord vos fichiers dans la barre latérale "
            "(page Performance ou ici).")
    st.stop()

flt = ui.page_header(df, title="Analyse des performances & recommandations")
if flt is None:
    st.stop()
start, end, comparison = flt

current, prev_df, prev_range = ui.resolve_periods(df, start, end, comparison)
if current.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

kpis = analytics.compute_kpis(current)
prev_kpis = analytics.compute_kpis(prev_df) if prev_df is not None else None

ui.pdf_export_button(current, prev_df, f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
                     comparison)

ui.scorecard_row(kpis, prev_kpis, ["Coût", "Revenus", "ROAS", "Conversions"])

# Constats automatiques
ui.section_band("Synthèse de la performance")
insights = analytics.build_insights(current, prev_df)
if not insights:
    st.info("Pas assez de données pour générer une analyse.")
else:
    left, right = st.columns(2)
    for i, ins in enumerate(insights):
        with (left if i % 2 == 0 else right):
            ui.insight_card(ins["level"], ins["title"], ins["detail"])

# Classement par rentabilité
ui.section_band("Classement par rentabilité (ROAS)")
st.caption("💡 Clique sur l'en-tête « ROAS » pour classer du plus au moins rentable.")
ui.interactive_table(analytics.comparison_table(current, prev_df, "campaign_type"),
                     "Type de campagne")

# Recommandations
ui.section_band("Recommandations actionnables")
st.caption("Priorisées par impact estimé, à partir des seules données de la "
           "période sélectionnée.")
for rc in analytics.build_recommendations(current, prev_df):
    ui.reco_card(rc["priority"], rc["action"], rc["rationale"])

# Détail par pays
ui.section_band("Détail par pays")
ui.interactive_table(analytics.comparison_table(current, prev_df, "country"), "Pays")
