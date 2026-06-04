"""Vue « Performance » — rapport mono-page façon Looker Studio."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import analytics, normalizer, ui

ui.inject_theme()

df = ui.sidebar_data_source()
if df is None or df.empty:
    st.title("📊 Dashboard de performances SEA")
    st.info("👈 Importez vos fichiers **(CSV, Excel ou PDF)** dans la barre "
            "latérale pour démarrer. Le dashboard lit uniquement les chiffres "
            "de vos fichiers.")
    st.stop()

flt = ui.sidebar_filters(df)
if flt is None:
    st.stop()
start, end, comparison = flt

st.sidebar.header("🧭 Segmentation")
segmentation = st.sidebar.radio(
    "Vue", ["Globale", "Géographique", "Par campagne"],
    label_visibility="collapsed", key="seg_view")

current, prev_df, prev_range = ui.resolve_periods(df, start, end, comparison)
if current.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

kpis = analytics.compute_kpis(current)
prev_kpis = analytics.compute_kpis(prev_df) if prev_df is not None else None

ui.pdf_export_button(current, prev_df, f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
                     comparison)

ui.header_band(f"{start:%d/%m/%Y} – {end:%d/%m/%Y}")
if comparison != "Aucune":
    if prev_kpis:
        st.caption(f"Comparaison · {comparison.lower()} : "
                   f"{prev_range[0]:%d/%m/%Y} → {prev_range[1]:%d/%m/%Y}")
    else:
        st.caption(f"Aucune donnée sur la {comparison.lower()} pour comparer.")

# Scorecards : Coût (investissement) en tête, puis les autres KPIs
ui.scorecard_row(kpis, prev_kpis,
                 ["Coût", "Clics", "CPC", "Conversions", "Revenus",
                  "Taux de conversion", "Panier Moyen", "ROAS"])

# Deux tableaux triables (clic sur l'en-tête) : par type de campagne, par zone
ui.section_band("Performance par type de campagne")
st.caption("💡 Clique sur un en-tête de colonne pour trier "
           "(1 clic = croissant, 2 clics = décroissant).")

# Filtre des types de campagne (facultatif)
all_types = sorted(current["campaign_type"].unique())
selected = st.multiselect("Filtrer les types de campagne", all_types,
                          default=all_types, key="camp_filter")
sel = selected or all_types
sub = current[current["campaign_type"].isin(sel)]
sub_prev = (prev_df[prev_df["campaign_type"].isin(sel)]
            if prev_df is not None else None)
ui.interactive_table(analytics.comparison_table(sub, sub_prev, "campaign_type"),
                     "Type de campagne")

ui.section_band("Performance par zone")
ui.breakdown_tiles(current, prev_df, "zone")
ui.interactive_table(analytics.comparison_table(current, prev_df, "zone"), "Zone")

# Donuts de répartition (par type de campagne)
agg = analytics.aggregate_by(current, "campaign_type")
cols = st.columns(4)
for col, (vc, lbl) in zip(cols, [("cost", "Coût"), ("clicks", "Clics"),
                                 ("conversions", "Conversions"),
                                 ("revenue", "Revenus")]):
    with col:
        st.plotly_chart(ui.donut(agg, "campaign_type", vc, lbl),
                        use_container_width=True)

# Graphique principal selon segmentation
ui.section_band("Évolution & répartition")
if segmentation == "Globale":
    st.plotly_chart(ui.daily_combo(current, prev_df), use_container_width=True)
elif segmentation == "Géographique":
    st.plotly_chart(ui.dimension_combo(current, "region", "Région"),
                    use_container_width=True)
else:
    st.plotly_chart(ui.dimension_combo(current, "campaign_type",
                    "Type de campagne"), use_container_width=True)

# Tendances mensuelles (avec comparaison)
cur_m = analytics.monthly_series(current)
prev_m = analytics.monthly_series(prev_df) if prev_df is not None else None
ui.section_band("Tendances mensuelles")
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(ui.combo_bar_line(cur_m, prev_m, "cost", "revenue",
                    "Coût", "Revenus", "Coût (barres) & Revenus (ligne)"),
                    use_container_width=True)
with c2:
    st.plotly_chart(ui.combo_bar_line(cur_m, prev_m, "cost", "conversions",
                    "Coût", "Conversions", "Coût (barres) & Conversions (ligne)"),
                    use_container_width=True)
st.plotly_chart(ui.lines(cur_m, prev_m,
                [("CPC", "CPC (€)", ui.THEME["primary"]),
                 ("ROAS", "ROAS", ui.THEME["accent"])],
                "CPC & ROAS par mois"), use_container_width=True)

with st.expander("🔍 Colonnes détectées & mapping (debug)"):
    detected = st.session_state.get("loaded_columns", {})
    if detected:
        for name, cols in detected.items():
            st.markdown(f"**{name}**")
            st.caption("Colonnes lues : " + ", ".join(map(str, cols)))
            mapping = normalizer.resolve_columns(cols)
            lignes = []
            for canon in ["date", "country", "campaign_type", "clicks",
                          "cost", "conversions", "revenue"]:
                src = mapping.get(canon)
                lignes.append(f"- **{canon}** ← {src if src else '❌ non trouvé'}")
            st.markdown("\n".join(lignes))
    st.caption(f"{len(current)} lignes sur la période.")
    st.dataframe(current, width="stretch")
