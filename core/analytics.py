"""Calcul des KPIs, comparaison de périodes et analyses pour les recommandations.

Règle absolue : les KPIs dérivés (CPC, ROAS, AOV) ne sont JAMAIS stockés ni
moyennés. Ils sont recalculés sur les TOTAUX après agrégation :
    * CPC  = coût total / clics totaux
    * ROAS = revenus    / coût
    * AOV  = revenus    / conversions
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

# Mesures brutes agrégeables (sommables). Aucun KPI dérivé ici.
_RAW = ["clicks", "cost", "conversions", "revenue"]


def _safe_div(numerator: float, denominator: float) -> float:
    """Division protégée : renvoie 0.0 si le dénominateur est nul."""
    if denominator in (0, 0.0) or pd.isna(denominator):
        return 0.0
    return float(numerator) / float(denominator)


def compute_kpis(df: pd.DataFrame) -> dict:
    """KPIs sur un DataFrame normalisé. Dérivés recalculés sur les totaux."""
    keys = ["Clics", "Coût", "Conversions", "Revenus", "CPC", "ROAS",
            "Panier Moyen", "Taux de conversion"]
    if df is None or df.empty:
        return {k: 0.0 for k in keys}

    clicks = float(df["clicks"].sum())
    cost = float(df["cost"].sum())
    conversions = float(df["conversions"].sum())
    revenue = float(df["revenue"].sum())

    return {
        "Clics": clicks,
        "Coût": cost,
        "Conversions": conversions,
        "Revenus": revenue,
        "CPC": _safe_div(cost, clicks),
        "ROAS": _safe_div(revenue, cost),
        "Panier Moyen": _safe_div(revenue, conversions),
        "Taux de conversion": _safe_div(conversions, clicks),
    }


def slice_period(df: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Filtre sur la plage [start, end] (bornes incluses)."""
    if df is None or df.empty:
        return df
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    return df.loc[(df["date"] >= start_ts) & (df["date"] <= end_ts)].copy()


def previous_period(start: dt.date, end: dt.date, mode: str):
    """Plage de comparaison.

    * "Période précédente" : même durée, juste avant.
    * "Année précédente"   : même plage, année N-1.
    * sinon                : None.
    """
    if mode == "Période précédente":
        duration = end - start
        prev_end = start - dt.timedelta(days=1)
        return prev_end - duration, prev_end
    if mode == "Année précédente":
        return _shift_year(start, -1), _shift_year(end, -1)
    return None


def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcule CPC/ROAS/AOV/CR sur les totaux de chaque ligne agrégée."""
    df["CPC"] = df.apply(lambda r: _safe_div(r["cost"], r["clicks"]), axis=1)
    df["ROAS"] = df.apply(lambda r: _safe_div(r["revenue"], r["cost"]), axis=1)
    df["AOV"] = df.apply(lambda r: _safe_div(r["revenue"], r["conversions"]), axis=1)
    df["CR"] = df.apply(lambda r: _safe_div(r["conversions"], r["clicks"]), axis=1)
    return df


def aggregate_by(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Agrège par dimension puis recalcule les KPIs dérivés sur les totaux.

    Colonnes : <dimension>, clicks, cost, conversions, revenue, CPC, ROAS, AOV.
    """
    cols = [dimension, *_RAW, "CPC", "ROAS", "AOV"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    grouped = df.groupby(dimension, as_index=False)[_RAW].sum()
    grouped = _add_derived(grouped)
    return grouped.sort_values("revenue", ascending=False).reset_index(drop=True)


def daily_series(df: pd.DataFrame) -> pd.DataFrame:
    """Agrégation par jour (vue Globale)."""
    cols = ["date", *_RAW, "CPC", "ROAS", "AOV"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    daily = df.groupby("date", as_index=False)[_RAW].sum().sort_values("date")
    return _add_derived(daily).reset_index(drop=True)


def monthly_series(df: pd.DataFrame) -> pd.DataFrame:
    """Agrégation par mois (combo charts façon Looker)."""
    cols = ["period", *_RAW, "CPC", "ROAS", "AOV"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    tmp = df.copy()
    tmp["period"] = tmp["date"].dt.to_period("M").dt.to_timestamp()
    monthly = tmp.groupby("period", as_index=False)[_RAW].sum().sort_values("period")
    return _add_derived(monthly).reset_index(drop=True)


# Métriques affichées dans les tableaux de comparaison (label + clé réelle).
TABLE_METRICS = [
    ("Coût", "cost"),
    ("Clics", "clicks"),
    ("CPC", "CPC"),
    ("Conversions", "conversions"),
    ("Revenus", "revenue"),
    ("Panier Moyen", "AOV"),
    ("CR", "CR"),
    ("ROAS", "ROAS"),
]
_KPI_NAME = {"cost": "Coût", "clicks": "Clics", "conversions": "Conversions",
             "revenue": "Revenus", "CPC": "CPC", "ROAS": "ROAS",
             "AOV": "Panier Moyen", "CR": "Taux de conversion"}


def comparison_table(current, previous, dimension: str) -> pd.DataFrame:
    """Tableau « à la Looker » : une ligne par valeur de la dimension, chaque
    métrique suivie de sa variation %Δ vs la comparaison, + ligne Grand total.
    """
    metrics = [k for _, k in TABLE_METRICS]
    cur = aggregate_by(current, dimension)
    prev = aggregate_by(previous, dimension) if previous is not None else None
    prev_idx = (prev.set_index(dimension)
                if prev is not None and not prev.empty else None)

    rows = []
    for _, r in cur.iterrows():
        row = {dimension: r[dimension]}
        for m in metrics:
            row[m] = r[m]
            row[f"{m}_delta"] = None
            if prev_idx is not None and r[dimension] in prev_idx.index:
                pv = prev_idx.loc[r[dimension], m]
                if pv not in (0, 0.0) and not pd.isna(pv):
                    row[f"{m}_delta"] = (r[m] - pv) / pv * 100
        rows.append(row)
    table = pd.DataFrame(rows)

    # Grand total : KPIs dérivés recalculés sur les totaux globaux.
    cur_tot = compute_kpis(current)
    prev_tot = compute_kpis(previous) if previous is not None else None
    total = {dimension: "Total général"}
    for m in metrics:
        total[m] = cur_tot[_KPI_NAME[m]]
        total[f"{m}_delta"] = None
        if prev_tot is not None:
            pv = prev_tot[_KPI_NAME[m]]
            if pv not in (0, 0.0):
                total[f"{m}_delta"] = (cur_tot[_KPI_NAME[m]] - pv) / pv * 100
    return pd.concat([table, pd.DataFrame([total])], ignore_index=True)


# --------------------------------------------------------------------------- #
# Analyse & recommandations (page 2)
# --------------------------------------------------------------------------- #
def kpi_deltas(current, previous) -> dict:
    """Variation %Δ de chaque KPI entre période courante et comparaison."""
    cur, prev = compute_kpis(current), compute_kpis(previous)
    out = {}
    for k in cur:
        base = prev.get(k, 0.0)
        out[k] = ((cur[k] - base) / base * 100) if base else None
    return out


def build_insights(current, previous=None) -> list[dict]:
    """Génère des constats automatiques (analyse) à partir des données.

    Chaque insight : {level: 'good'|'warn'|'bad'|'info', title, detail}.
    """
    insights: list[dict] = []
    if current is None or current.empty:
        return insights

    k = compute_kpis(current)
    by_camp = aggregate_by(current, "campaign_type")
    by_country = aggregate_by(current, "country")

    # 1. ROAS global
    roas = k["ROAS"]
    if roas >= 4:
        insights.append(dict(level="good", title=f"ROAS global solide ({roas:.2f}x)",
            detail="Le retour sur dépense publicitaire est sain : "
                   "chaque euro investi génère "
                   f"{roas:.2f} € de revenus."))
    elif roas >= 2:
        insights.append(dict(level="warn", title=f"ROAS global moyen ({roas:.2f}x)",
            detail="Le ROAS est correct mais améliorable. Concentrez le budget "
                   "sur les segments les plus rentables."))
    else:
        insights.append(dict(level="bad", title=f"ROAS global faible ({roas:.2f}x)",
            detail="La rentabilité est sous le seuil de 2x. Revoyez le ciblage, "
                   "les enchères et les pages de destination."))

    # 2. Évolution vs comparaison
    if previous is not None and not previous.empty:
        d = kpi_deltas(current, previous)
        for key, kw in (("Revenus", "des revenus"), ("ROAS", "du ROAS"),
                        ("CPC", "du CPC")):
            dv = d.get(key)
            if dv is None:
                continue
            improving = dv > 0 if key != "CPC" else dv < 0
            lvl = "good" if improving else "bad"
            sense = "hausse" if dv > 0 else "baisse"
            insights.append(dict(level=lvl,
                title=f"Évolution {kw} : {dv:+.1f}%",
                detail=f"{key} en {sense} vs période de comparaison."))

    # 3. Meilleure / pire campagne par ROAS
    if not by_camp.empty:
        best = by_camp.loc[by_camp["ROAS"].idxmax()]
        worst = by_camp.loc[by_camp["ROAS"].idxmin()]
        insights.append(dict(level="good",
            title=f"Campagne la plus rentable : {best['campaign_type']}",
            detail=f"ROAS {best['ROAS']:.2f}x pour {best['revenue']:,.0f} € "
                   f"de revenus.".replace(",", " ")))
        if worst["campaign_type"] != best["campaign_type"]:
            insights.append(dict(level="warn",
                title=f"Campagne à surveiller : {worst['campaign_type']}",
                detail=f"ROAS {worst['ROAS']:.2f}x — la moins rentable du mix."))

    # 4. Concentration du coût
    if not by_country.empty:
        top = by_country.iloc[0]
        share = _safe_div(top["cost"], k["Coût"]) * 100
        if share >= 30:
            insights.append(dict(level="info",
                title=f"Dépense concentrée sur « {top['country']} »",
                detail=f"{share:.0f}% du budget total. "
                       "Vérifiez que la diversification géographique est voulue."))

    return insights


def build_recommendations(current, previous=None) -> list[dict]:
    """Recommandations actionnables, dérivées des données.

    Chaque reco : {priority: 'haute'|'moyenne'|'basse', action, rationale}.
    """
    recos: list[dict] = []
    if current is None or current.empty:
        return recos

    by_camp = aggregate_by(current, "campaign_type")
    by_country = aggregate_by(current, "country")
    k = compute_kpis(current)
    median_roas = by_camp["ROAS"].median() if not by_camp.empty else 0

    # Budget : pousser les segments rentables, couper les non rentables.
    for _, r in by_camp.iterrows():
        if r["ROAS"] >= max(4, median_roas) and r["revenue"] > 0:
            recos.append(dict(priority="haute",
                action=f"Augmenter le budget de « {r['campaign_type']} »",
                rationale=f"ROAS {r['ROAS']:.2f}x au-dessus de la médiane "
                          f"({median_roas:.2f}x) : marge de scale rentable."))
        elif r["ROAS"] < 2 and r["cost"] > 0:
            recos.append(dict(priority="haute",
                action=f"Réduire / restructurer « {r['campaign_type']} »",
                rationale=f"ROAS {r['ROAS']:.2f}x sous le seuil de rentabilité : "
                          f"{r['cost']:,.0f} € dépensés pour un retour faible."
                          .replace(",", " ")))

    # Pays : CPC élevé + ROAS faible → optimiser enchères.
    if not by_country.empty:
        cpc_med = by_country["CPC"].median()
        for _, r in by_country.iterrows():
            if r["CPC"] > cpc_med * 1.3 and r["ROAS"] < median_roas and r["cost"] > 0:
                recos.append(dict(priority="moyenne",
                    action=f"Optimiser les enchères sur « {r['country']} »",
                    rationale=f"CPC élevé ({r['CPC']:.2f} €) et ROAS faible "
                              f"({r['ROAS']:.2f}x) : le trafic coûte cher pour "
                              "un retour limité."))

    # Panier moyen faible → ventes additionnelles / montée en gamme.
    if k["Panier Moyen"] and k["Panier Moyen"] < 50:
        recos.append(dict(priority="moyenne",
            action="Travailler le panier moyen (ventes additionnelles)",
            rationale=f"Panier moyen de {k['Panier Moyen']:.0f} € : des offres "
                      "groupées ou des seuils de livraison gratuite peuvent "
                      "l'augmenter."))

    if not recos:
        recos.append(dict(priority="basse",
            action="Maintenir la stratégie actuelle",
            rationale="Aucun signal critique détecté sur la période : "
                      "performances équilibrées."))
    return recos


# --------------------------------------------------------------------------- #
# Analyses avancées (page « Analyses avancées »)
# --------------------------------------------------------------------------- #
# Métriques disponibles pour les croisements et la matrice.
METRIC_KEYS = {
    "Revenus": "revenue", "Coût": "cost", "Clics": "clicks",
    "Conversions": "conversions", "ROAS": "ROAS", "CPC": "CPC",
    "Panier Moyen": "AOV",
}
_DERIVED = {"ROAS", "CPC", "AOV"}


def pivot(df: pd.DataFrame, index: str, columns: str, metric_label: str):
    """Tableau croisé `index × columns` pour une métrique.

    Les mesures brutes sont sommées par cellule ; les KPIs dérivés (ROAS, CPC,
    AOV) sont **recalculés sur les totaux de chaque cellule** (jamais moyennés).
    Renvoie un DataFrame pivoté (index en lignes, colonnes en colonnes).
    """
    key = METRIC_KEYS[metric_label]
    if df is None or df.empty:
        return pd.DataFrame()
    grp = df.groupby([index, columns], as_index=False)[_RAW].sum()
    grp = _add_derived(grp)
    return grp.pivot(index=index, columns=columns, values=key)


def performance_matrix(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Données pour la matrice de performance (Coût vs Revenus, ROAS, conv.)."""
    return aggregate_by(df, dimension)


def pareto(df: pd.DataFrame, dimension: str, metric_label: str = "Revenus"):
    """Contribution cumulée (Pareto) par dimension sur une métrique brute."""
    key = METRIC_KEYS[metric_label]
    agg = aggregate_by(df, dimension)
    if agg.empty:
        return agg
    agg = agg.sort_values(key, ascending=False).reset_index(drop=True)
    total = agg[key].sum()
    agg["part"] = agg[key] / total * 100 if total else 0.0
    agg["cumul"] = agg["part"].cumsum()
    return agg


def detect_anomalies(df: pd.DataFrame, metric: str = "ROAS", z: float = 2.0):
    """Détecte les jours atypiques sur une série quotidienne (écart > z·σ).

    Renvoie un DataFrame des jours anormaux avec l'écart à la moyenne, trié par
    amplitude décroissante.
    """
    daily = daily_series(df)
    if daily.empty or len(daily) < 3:
        return pd.DataFrame(columns=["date", metric, "moyenne", "ecart_sigma"])
    series = daily[metric].astype(float)
    mean, std = series.mean(), series.std(ddof=0)
    if std == 0:
        return pd.DataFrame(columns=["date", metric, "moyenne", "ecart_sigma"])
    daily["moyenne"] = mean
    daily["ecart_sigma"] = (series - mean) / std
    out = daily[daily["ecart_sigma"].abs() >= z][
        ["date", metric, "moyenne", "ecart_sigma"]]
    return out.reindex(out["ecart_sigma"].abs().sort_values(ascending=False).index)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _shift_year(d: dt.date, delta: int) -> dt.date:
    try:
        return d.replace(year=d.year + delta)
    except ValueError:
        return d.replace(year=d.year + delta, day=28)
