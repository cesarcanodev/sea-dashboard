"""Calcul des KPIs, comparaison de périodes et analyses pour les recommandations.

Règle absolue : les KPIs dérivés (CPC, ROAS, AOV) ne sont JAMAIS stockés ni
moyennés. Ils sont recalculés sur les TOTAUX après agrégation :
    * CPC  = coût total / clics totaux
    * ROAS = revenus    / coût
    * AOV  = revenus    / conversions
"""

from __future__ import annotations

import datetime as dt
import math
import re

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


# --------------------------------------------------------------------------- #
# Lecture « senior » : classification des leviers, nomenclatures, drivers
# --------------------------------------------------------------------------- #
# Tokens de période commerciale (soldes, ventes privées, temps forts).
_SALES_TOKENS = ("sales", "sale", "soldes", "solde", "promo", "promotion",
                 "black friday", "blackfriday", "cyber", "outlet", "destockage",
                 "déstockage", "ventes privees", "ventes privées", "vente privee",
                 "private sale")
_DEDICATED_TOKENS = ("dedie", "dédié", "dedicated", "dédiée", "dedie", "drop",
                     "launch", "lancement", "capsule", "collab", "teaser")


def _eur(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") + " €"


def _is_brand_label(label: str) -> bool:
    """True pour les leviers de marque (Pure Brand, Branded, Brex, Search Brand).
    « Brand Other » est un levier hors-marque (générique) → False."""
    l = str(label).lower()
    if "other" in l:
        return False
    return ("brand" in l) or ("brex" in l) or ("marque" in l)


def _name_has(series: pd.Series, tokens) -> pd.Series:
    pat = "|".join(re.escape(t) for t in tokens)
    return series.astype(str).str.lower().str.contains(pat, regex=True, na=False)


def split_brand(df: pd.DataFrame):
    """Renvoie (kpis_marque, kpis_hors_marque) d'après le type de campagne."""
    if df is None or df.empty:
        return None, None
    is_b = df["campaign_type"].map(_is_brand_label)
    return compute_kpis(df[is_b]), compute_kpis(df[~is_b.values])


def sales_context(df: pd.DataFrame):
    """Part de budget sur des campagnes Sales/Soldes (via le nom complet)."""
    if df is None or df.empty or "campaign_name" not in df.columns:
        return None
    mask = _name_has(df["campaign_name"], _SALES_TOKENS)
    if not mask.any():
        return None
    k = compute_kpis(df[mask.values])
    return {"share": _safe_div(df.loc[mask.values, "cost"].sum(), df["cost"].sum()),
            "roas": k["ROAS"], "aov": k["Panier Moyen"],
            "revenue": k["Revenus"], "cost": k["Coût"]}


def roas_drivers(current, previous):
    """Décompose la variation du ROAS en contributions CR / panier / CPC.

    ROAS = (CR × AOV) / CPC. On renvoie les %Δ de chaque facteur et le driver
    dominant (en log-amplitude), pour une lecture « cause → effet » senior.
    """
    if previous is None or previous.empty:
        return None
    c, p = compute_kpis(current), compute_kpis(previous)
    keys = ("ROAS", "Taux de conversion", "Panier Moyen", "CPC", "Clics",
            "Revenus", "Conversions")
    out = {key: (((c[key] - p[key]) / p[key] * 100) if p[key] else None)
           for key in keys}
    contribs = {}
    for key, sign in (("Taux de conversion", 1), ("Panier Moyen", 1), ("CPC", -1)):
        if p[key] > 0 and c[key] > 0:
            contribs[key] = sign * math.log(c[key] / p[key])
    out["dominant"] = (max(contribs, key=lambda x: abs(contribs[x]))
                       if contribs else None)
    return out


_DRIVER_LABEL = {"Taux de conversion": "le taux de conversion",
                 "Panier Moyen": "le panier moyen", "CPC": "le CPC"}


def build_insights(current, previous=None) -> list[dict]:
    """Constats automatiques — lecture niveau consultant senior Google Ads.

    Chaque insight : {level: 'good'|'warn'|'bad'|'info', title, detail}.
    """
    insights: list[dict] = []
    if current is None or current.empty:
        return insights

    k = compute_kpis(current)
    roas = k["ROAS"]
    by_camp = aggregate_by(current, "campaign_type")
    zone_dim = "zone" if "zone" in current.columns else "country"
    by_zone = aggregate_by(current, zone_dim)

    # 1. Dépendance à la marque (lecture clé d'un compte retail/luxe)
    bk, nbk = split_brand(current)
    if bk and nbk and bk["Coût"] > 0 and nbk["Coût"] > 0:
        br = _safe_div(bk["Revenus"], k["Revenus"]) * 100
        bc = _safe_div(bk["Coût"], k["Coût"]) * 100
        insights.append(dict(level="info",
            title=f"ROAS {roas:.2f}x — marque {bk['ROAS']:.1f}x / hors-marque "
                  f"{nbk['ROAS']:.1f}x",
            detail=(f"La marque pèse {br:.0f}% du CA pour {bc:.0f}% du coût : elle "
                    "capte une demande existante et tire le ROAS global vers le "
                    f"haut. L'acquisition réelle se joue hors-marque (ROAS "
                    f"{nbk['ROAS']:.2f}x, {_eur(nbk['Coût'])} investis) — c'est "
                    "le levier à challenger en priorité.")))
    else:
        lvl = "good" if roas >= 4 else ("warn" if roas >= 2 else "bad")
        insights.append(dict(level=lvl, title=f"ROAS global {roas:.2f}x",
            detail=f"Chaque euro investi génère {roas:.2f} € de CA "
                   f"({_eur(k['Coût'])} de coût pour {_eur(k['Revenus'])})."))

    # 2. Décomposition de la variation du ROAS (driver principal)
    if previous is not None and not previous.empty:
        drv = roas_drivers(current, previous)
        if drv and drv["ROAS"] is not None:
            cr, aov, cpc = (drv["Taux de conversion"], drv["Panier Moyen"],
                            drv["CPC"])
            dom = _DRIVER_LABEL.get(drv["dominant"], "")
            lvl = "good" if drv["ROAS"] >= 0 else "warn"
            bits = []
            if cr is not None:
                bits.append(f"CR {cr:+.0f}%")
            if aov is not None:
                bits.append(f"panier {aov:+.0f}%")
            if cpc is not None:
                bits.append(f"CPC {cpc:+.0f}%")
            tail = f" Driver principal : {dom}." if dom else ""
            insights.append(dict(level=lvl,
                title=f"ROAS {drv['ROAS']:+.0f}% vs comparaison",
                detail=(f"Décomposition (ROAS = CR × panier ÷ CPC) : "
                        f"{', '.join(bits)}.{tail} "
                        f"CA {drv['Revenus']:+.0f}% pour un trafic "
                        f"{drv['Clics']:+.0f}%.")))

    # 3. Contexte commercial : soldes / ventes privées
    sc = sales_context(current)
    if sc and sc["share"] >= 0.10:
        insights.append(dict(level="info",
            title=f"Période commerciale active ({sc['share']*100:.0f}% du budget "
                  "en Sales/Soldes)",
            detail=(f"Les campagnes Sales pèsent {sc['share']*100:.0f}% de la "
                    f"dépense (ROAS {sc['roas']:.2f}x, panier {sc['aov']:.0f} €). "
                    "Volume en hausse et panier/ROAS mécaniquement sous pression : "
                    "à lire dans ce contexte, pas comme une dégradation de fond.")))

    # 4. Meilleur / pire levier avec lecture d'efficience
    if len(by_camp) >= 2:
        best = by_camp.loc[by_camp["ROAS"].idxmax()]
        worst = by_camp.loc[by_camp[by_camp["cost"] > 0]["ROAS"].idxmin()]
        insights.append(dict(level="good",
            title=f"Levier le plus rentable : {best['campaign_type']} "
                  f"({best['ROAS']:.2f}x)",
            detail=f"{_eur(best['revenue'])} de CA, panier {best['AOV']:.0f} €, "
                   f"CR {best['CR']*100:.2f}%."))
        if worst["campaign_type"] != best["campaign_type"]:
            insights.append(dict(level="warn",
                title=f"Levier sous-performant : {worst['campaign_type']} "
                      f"({worst['ROAS']:.2f}x)",
                detail=f"{_eur(worst['cost'])} dépensés, CPC {worst['CPC']:.2f} €, "
                       f"CR {worst['CR']*100:.2f}% — efficience à challenger."))

    # 5. Concentration géographique
    if not by_zone.empty and k["Coût"] > 0:
        top = by_zone.iloc[0]
        share = _safe_div(top["cost"], k["Coût"]) * 100
        if share >= 35:
            insights.append(dict(level="info",
                title=f"Dépense concentrée sur « {top[zone_dim]} » ({share:.0f}%)",
                detail=f"ROAS {top['ROAS']:.2f}x sur cette zone. "
                       "Un aléa local impacte fortement le global — surveiller."))

    return insights


def build_recommendations(current, previous=None) -> list[dict]:
    """Recommandations actionnables et chiffrées (niveau senior).

    Chaque reco : {priority: 'haute'|'moyenne'|'basse', action, rationale}.
    """
    recos: list[dict] = []
    if current is None or current.empty:
        return recos

    # 0. Diagnostics d'enchères (si stratégies/cibles disponibles via Google Ads)
    recos.extend(bidding_diagnostics(current))

    by_camp = aggregate_by(current, "campaign_type")
    k = compute_kpis(current)
    zone_dim = "zone" if "zone" in current.columns else "country"
    by_zone = aggregate_by(current, zone_dim)
    median_roas = by_camp["ROAS"].median() if not by_camp.empty else 0

    # 1. Réallocation budgétaire chiffrée (scale rentable / coupe non rentable)
    for _, r in by_camp.iterrows():
        if r["ROAS"] >= max(4, median_roas * 1.2) and r["revenue"] > 0:
            recos.append(dict(priority="haute",
                action=f"Scaler « {r['campaign_type']} » (+15 à +25% de budget)",
                rationale=f"ROAS {r['ROAS']:.2f}x > médiane {median_roas:.2f}x et "
                          f"{_eur(r['revenue'])} de CA : marge de croissance "
                          "rentable, monter par paliers de 20% en surveillant le "
                          "ROAS marginal."))
        elif r["ROAS"] < 2 and r["cost"] > 0:
            recos.append(dict(priority="haute",
                action=f"Restructurer / réallouer « {r['campaign_type']} »",
                rationale=f"ROAS {r['ROAS']:.2f}x sous le seuil de rentabilité pour "
                          f"{_eur(r['cost'])} : revoir requêtes, audiences et "
                          "enchères, ou basculer le budget vers les leviers > médiane."))

    # 2. Dépendance marque → effort acquisition hors-marque
    bk, nbk = split_brand(current)
    if bk and nbk and bk["Coût"] > 0 and nbk["Coût"] > 0:
        bc = _safe_div(bk["Coût"], k["Coût"]) * 100
        if bc >= 35 and nbk["ROAS"] >= 1.5:
            recos.append(dict(priority="moyenne",
                action="Renforcer l'acquisition hors-marque (Gen, PMax, Shopping)",
                rationale=f"La marque concentre {bc:.0f}% du budget. Le hors-marque "
                          f"tient un ROAS de {nbk['ROAS']:.2f}x : il y a de la place "
                          "pour aller chercher de la nouvelle demande sans diluer "
                          "la rentabilité."))

    # 3. Zone : CPC élevé + ROAS faible → enchères / ciblage
    if not by_zone.empty:
        cpc_med = by_zone["CPC"].median()
        for _, r in by_zone.iterrows():
            if r["CPC"] > cpc_med * 1.3 and r["ROAS"] < median_roas and r["cost"] > 0:
                recos.append(dict(priority="moyenne",
                    action=f"Resserrer les enchères sur « {r[zone_dim]} »",
                    rationale=f"CPC {r['CPC']:.2f} € (+{(_safe_div(r['CPC'], cpc_med)-1)*100:.0f}% "
                              f"vs médiane) pour un ROAS {r['ROAS']:.2f}x : le trafic "
                              "y coûte cher pour un retour limité."))

    # 4. Anticipation des temps forts commerciaux
    sc = sales_context(current)
    if sc and sc["share"] >= 0.10:
        recos.append(dict(priority="basse",
            action="Cadrer les campagnes Sales (budgets + tROAS dédiés)",
            rationale=f"{sc['share']*100:.0f}% du budget est sur des campagnes "
                      "Sales : prévoir des budgets et des cibles d'enchères "
                      "spécifiques sur ces périodes, et isoler leur lecture du "
                      "BAU pour ne pas fausser les tendances de fond."))

    if not recos:
        recos.append(dict(priority="basse",
            action="Maintenir la trajectoire actuelle",
            rationale="Aucun signal critique : mix équilibré et rentabilité saine "
                      "sur la période."))
    return recos


def bidding_diagnostics(df: pd.DataFrame) -> list[dict]:
    """Diagnostics par campagne basés sur la stratégie d'enchères et les cibles
    (tROAS / tCPA) — disponibles via la connexion Google Ads. Renvoie [] si ces
    informations ne sont pas présentes (ex. imports Excel sans stratégie)."""
    recos: list[dict] = []
    if (df is None or df.empty or "bidding_strategy" not in df.columns
            or "campaign_name" not in df.columns):
        return recos
    if not df["bidding_strategy"].astype(str).str.strip().any():
        return recos

    g = df.groupby("campaign_name", as_index=False).agg(
        cost=("cost", "sum"), conv=("conversions", "sum"),
        rev=("revenue", "sum"), strat=("bidding_strategy", "first"),
        troas=("target_roas", "max"), tcpa=("target_cpa", "max"))

    for _, r in g.iterrows():
        if r["cost"] <= 0:
            continue
        roas = _safe_div(r["rev"], r["cost"])
        name = r["campaign_name"]
        if r["troas"] and r["troas"] > 0:                      # campagne en tROAS
            tgt = float(r["troas"])
            if roas < tgt * 0.7:
                recos.append(dict(priority="haute",
                    action=f"Abaisser la tROAS de « {name} »",
                    rationale=f"ROAS réel {roas:.2f}x très en deçà de la cible "
                              f"{tgt:.2f}x : l'algo se restreint et bride le volume. "
                              f"Baisser la cible (~{roas*1.1:.1f}x) pour rouvrir la "
                              "diffusion, puis remonter par paliers."))
            elif roas > tgt * 1.3:
                recos.append(dict(priority="moyenne",
                    action=f"Exploiter la marge de « {name} »",
                    rationale=f"ROAS réel {roas:.2f}x au-dessus de la cible "
                              f"{tgt:.2f}x : marge pour augmenter le budget ou "
                              "gagner du volume en abaissant légèrement la tROAS."))
        elif r["tcpa"] and r["tcpa"] > 0 and r["conv"] > 0:    # campagne en tCPA
            cpa = _safe_div(r["cost"], r["conv"])
            if cpa > r["tcpa"] * 1.3:
                recos.append(dict(priority="haute",
                    action=f"Ajuster la tCPA de « {name} »",
                    rationale=f"CPA réel {cpa:.0f} € au-dessus de la cible "
                              f"{r['tcpa']:.0f} € : resserrer le ciblage/la qualité "
                              "du trafic ou réaligner la cible."))
        else:                                                  # pas de cible valeur
            strat = str(r["strat"]).upper()
            if any(s in strat for s in ("MAXIMIZE_CONVERSION", "MAXIMIZE CONVERSION",
                                        "MAXIMIZE_CLICKS", "MAXIMIZE CLICKS",
                                        "MANUAL")) and r["rev"] > 0:
                recos.append(dict(priority="moyenne",
                    action=f"Passer « {name} » en tROAS",
                    rationale=f"Stratégie « {r['strat']} » sans cible de valeur "
                              f"alors que la campagne génère du CA (ROAS {roas:.2f}x) "
                              ": une tROAS piloterait mieux la rentabilité."))
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
