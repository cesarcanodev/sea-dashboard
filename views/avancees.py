"""Vue « Analyses avancées » — croisements et outils d'investigation.

Prolonge le rapport de base : tableau croisé pays × campagne, matrice de
performance, Pareto de contribution au CA, et détection d'anomalies. Utilise la
même période et la même comparaison que les autres onglets (filtres partagés).
"""

from __future__ import annotations

import streamlit as st

from core import analytics, ui

ui.inject_theme()

df = ui.sidebar_data_source()
if df is None or df.empty:
    st.title("🧪 Analyses avancées")
    st.info("👈 Importez d'abord vos fichiers dans la barre latérale.")
    st.stop()

flt = ui.page_header(df, title="Analyses avancées")
if flt is None:
    st.stop()
start, end, comparison = flt

current, prev_df, prev_range = ui.resolve_periods(df, start, end, comparison)
if current.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

ui.pdf_export_button(current, prev_df, f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
                     comparison)

# --- Tableau croisé pays × campagne ---
ui.section_band("Tableau croisé — Pays × Type de campagne")
metric = st.selectbox("Métrique à croiser", list(analytics.METRIC_KEYS.keys()),
                      index=0, key="adv_metric")
piv = analytics.pivot(current, "country", "campaign_type", metric)
st.plotly_chart(ui.heatmap(piv, f"{metric} par pays et type de campagne", metric),
                use_container_width=True)

# --- Matrice de performance ---
ui.section_band("Matrice de performance")
st.caption("Chaque bulle = un pays · X : Coût · Y : Revenus · couleur : ROAS · "
           "taille : conversions. En haut à gauche = très rentable, "
           "en bas à droite = à optimiser.")
st.plotly_chart(ui.perf_scatter(analytics.performance_matrix(current, "country"),
                "country", "Par pays"), use_container_width=True)
st.plotly_chart(ui.perf_scatter(
    analytics.performance_matrix(current, "campaign_type"),
    "campaign_type", "Par type de campagne"), use_container_width=True)

# --- Pareto ---
ui.section_band("Contribution au chiffre d'affaires (Pareto)")
st.caption("Part cumulée des revenus par pays. La ligne pointillée marque le "
           "seuil des 80 %.")
st.plotly_chart(ui.pareto_chart(analytics.pareto(current, "country", "Revenus"),
                "country", "Revenus"), use_container_width=True)

# --- Détection d'anomalies ---
ui.section_band("Détection d'anomalies — ROAS quotidien")
anom = analytics.detect_anomalies(current, metric="ROAS", z=2.0)
if anom.empty:
    st.success("Aucun jour atypique détecté (écart < 2σ) sur le ROAS quotidien.")
else:
    st.caption(f"{len(anom)} jour(s) au comportement atypique (écart ≥ 2σ "
               "par rapport à la moyenne de la période).")
    show = anom.copy()
    show["date"] = show["date"].dt.strftime("%d/%m/%Y")
    show["ROAS"] = show["ROAS"].map(lambda v: f"{v:.2f}x")
    show["moyenne"] = show["moyenne"].map(lambda v: f"{v:.2f}x")
    show["ecart_sigma"] = show["ecart_sigma"].map(lambda v: f"{v:+.1f} σ")
    show = show.rename(columns={"date": "Date", "moyenne": "Moyenne période",
                                "ecart_sigma": "Écart"})
    st.dataframe(show, width="stretch", hide_index=True)
