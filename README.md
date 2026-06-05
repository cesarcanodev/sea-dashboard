# 📊 Dashboard SEA (Search Engine Advertising)

Dashboard **Streamlit multipage** pour analyser les performances de campagnes
SEA à partir de **vos propres fichiers** (CSV, Excel ou PDF). Il normalise des
sources hétérogènes (en-têtes FR/EN, format de nombres français) vers un schéma
canonique, puis présente les résultats avec une charte sobre et professionnelle
inspirée de Looker Studio (palette « Stormy morning »).

> **Données** : le dashboard lit uniquement les chiffres des fichiers que vous
> importez. Aucune donnée n'est inventée ni transformée — seuls le nettoyage de
> format (espaces, virgule décimale, €) et le mapping de colonnes sont appliqués.

## Pages

1. **Performance** — vue d'ensemble : scorecards (6 KPIs), tableaux de
   comparaison (`% Δ` + *Total général*), donuts, tuiles par région, tableau
   par pays, et graphiques adaptés à la segmentation.
2. **Analyse & Recommandations** — constats automatiques + recommandations
   actionnables priorisées.
3. **Analyses avancées** — tableau croisé pays × campagne, matrice de
   performance, Pareto de contribution au CA, détection d'anomalies (ROAS).

La **période** et le **mode de comparaison** sont **partagés entre toutes les
pages** (un seul réglage s'applique partout). Un bouton **« Générer le rapport
PDF »** produit une synthèse client téléchargeable.

## KPIs suivis

**Clics · CPC · Conversions · Revenus · ROAS · Panier Moyen**

> Les indicateurs dérivés (CPC, ROAS, Panier Moyen) ne sont jamais stockés ni
> moyennés : ils sont **recalculés sur les totaux** après agrégation
> (`CPC = coût / clics`, `ROAS = revenus / coût`, `Panier Moyen = revenus / conversions`).

## Format de fichier attendu

En-têtes reconnus (FR ou EN), par exemple :

```
Date ; Pays ; Type de campagne ; Clics ; Coût ; Conversions ; Revenus
```

Schéma canonique cible :

```
date · country · region · campaign_type · clicks · cost · conversions · revenue
```

## Installation

```bash
cd sea-dashboard
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

Importez vos fichiers dans la barre latérale, réglez la période, puis naviguez
entre les trois pages via le menu en haut de la sidebar.

## Personnalisation

La charte (couleurs, marque, titre) est centralisée dans le dict `THEME` en
haut de [`core/ui.py`](core/ui.py).

## Structure

```
sea-dashboard/
├── app.py                  # point d'entrée multipage (st.navigation)
├── views/
│   ├── performance.py      # page 1 : performance overview
│   ├── analyse.py          # page 2 : analyse & recommandations
│   └── avancees.py         # page 3 : analyses avancées
├── core/
│   ├── ui.py               # thème, composants, graphiques, sidebar
│   ├── readers.py          # lecture CSV / Excel / PDF
│   ├── normalizer.py       # mapping colonnes + pays→région
│   ├── analytics.py        # KPIs, comparaison, croisements, insights
│   └── export.py           # génération du rapport PDF (reportlab)
├── .streamlit/config.toml  # thème clair (fond blanc)
├── requirements.txt
└── README.md
```
