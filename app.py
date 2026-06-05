"""Dashboard de performances SEA — point d'entrée multipage.

Trois pages, charte visuelle commune (façon Looker Studio) :
    1. Performance  — KPIs, comparaison, segmentation, graphiques.
    2. Analyse & Recommandations — constats automatiques + actions.
    3. Analyses avancées — croisements, matrice de performance, Pareto, anomalies.

Lancement :
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from core import ui

st.set_page_config(page_title="Dashboard SEA", page_icon="📊", layout="wide")
ui.inject_theme()

pages = st.navigation([
    st.Page("views/performance.py", title="Performance", icon="📊", default=True),
    st.Page("views/analyse.py", title="Analyse & Recommandations", icon="🔍"),
    st.Page("views/avancees.py", title="Analyses avancées", icon="🧪"),
    st.Page("views/rapport.py", title="Rapport client", icon="📧"),
])
pages.run()
