"""Génération automatique du compte-rendu / email client (texte).

Produit un texte français prêt à copier-coller dans un email, rempli avec les
vrais chiffres de la période : KPIs (avec WoW), performance par zone et par
levier, constats et recommandations. La narration est pilotée par les données ;
l'utilisateur peut ensuite éditer le texte avant envoi.
"""

from __future__ import annotations

from core import analytics


# --------------------------------------------------------------------------- #
# Formatage (sans dépendance Streamlit)
# --------------------------------------------------------------------------- #
def _eur(v):
    return f"{v:,.0f}".replace(",", " ") + " €"


def _cpc(v):
    return f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", " ") + " €"


def _int(v):
    return f"{v:,.0f}".replace(",", " ")


def _roas(v):
    return f"{v:.2f}".replace(".", ",")


def _pct(v):
    return f"{v * 100:.2f}".replace(".", ",") + " %"


def _delta(d):
    if d is None:
        return ""
    return f" ({d:+.0f} %)"


def _pct_change(cur, prev):
    if prev in (None, 0, 0.0):
        return None
    return (cur - prev) / prev * 100


def _share(part, total):
    return 0 if not total else part / total * 100


# --------------------------------------------------------------------------- #
# Génération
# --------------------------------------------------------------------------- #
def build_email(current, prev_df, period_label, comparison) -> str:
    """Construit le texte du compte-rendu client."""
    k = analytics.compute_kpis(current)
    kp = analytics.compute_kpis(prev_df) if prev_df is not None else None
    d = {key: _pct_change(k[key], kp[key]) for key in k} if kp else {key: None for key in k}
    has_comp = kp is not None and comparison != "Aucune"

    L = []  # lignes du mail
    L.append("Bonjour,")
    L.append("")
    intro = f"Voici le point performance SEA sur la période {period_label}"
    if has_comp:
        intro += f", comparé à la {comparison.lower()}"
    L.append(intro + ".")
    L.append("")

    # ---- Synthèse globale (narratif) ----
    L.append("— Vue d'ensemble —")
    roas_txt = f"Le ROAS Server Side ressort à {_roas(k['ROAS'])}"
    if has_comp and d["ROAS"] is not None:
        roas_txt += f" ({d['ROAS']:+.0f} % vs période de comparaison)"
    L.append(roas_txt + ".")

    if has_comp and d["Clics"] is not None:
        traf = ("quasi stable" if abs(d["Clics"]) < 3
                else ("en progression" if d["Clics"] > 0 else "en recul"))
        phrase = f"Le trafic est {traf} ({d['Clics']:+.0f} % de clics)"
        if d["CPC"] is not None:
            sens = "en baisse" if d["CPC"] < 0 else "en hausse"
            phrase += f", avec un CPC {sens} de {abs(d['CPC']):.0f} %"
        L.append(phrase + ".")
        if d["Conversions"] is not None:
            cv = "progressent" if d["Conversions"] > 0 else "reculent"
            cphrase = f"Les conversions {cv} de {abs(d['Conversions']):.0f} %"
            if d["Panier Moyen"] is not None:
                cphrase += (f", avec un panier moyen à {_eur(k['Panier Moyen'])} "
                            f"({d['Panier Moyen']:+.0f} %)")
            L.append(cphrase + ".")
    L.append("")

    # ---- Récap KPIs ----
    L.append("Récap KPIs :")
    for label in ["Coût", "Clics", "CPC", "Conversions", "Revenus",
                  "Taux de conversion", "Panier Moyen", "ROAS"]:
        val = (_eur(k[label]) if label in ("Coût", "Revenus", "Panier Moyen")
               else _cpc(k[label]) if label == "CPC"
               else _pct(k[label]) if label == "Taux de conversion"
               else _roas(k[label]) if label == "ROAS"
               else _int(k[label]))
        L.append(f"  • {label} : {val}{_delta(d[label]) if has_comp else ''}")
    L.append("")

    # ---- Par zone ----
    L.append("— Performance par zone —")
    zt = analytics.aggregate_by(current, "zone")
    zprev = (analytics.aggregate_by(prev_df, "zone")
             if prev_df is not None else None)
    zprev_rev = (zprev.set_index("zone")["revenue"].to_dict()
                 if zprev is not None and not zprev.empty else {})
    total_rev = k["Revenus"]
    for _, r in zt.iterrows():
        dd = _pct_change(r["revenue"], zprev_rev.get(r["zone"]))
        L.append(f"  • {r['zone']} : Coût {_eur(r['cost'])} · Clics "
                 f"{_int(r['clicks'])} · CA {_eur(r['revenue'])}"
                 f"{_delta(dd) if has_comp else ''} · ROAS {_roas(r['ROAS'])}")
    if not zt.empty:
        top = zt.iloc[0]
        L.append("")
        L.append(f"{top['zone']} concentre {_share(top['revenue'], total_rev):.0f} % "
                 f"du CA et reste la zone la plus contributrice (ROAS "
                 f"{_roas(top['ROAS'])}).")
        worst = zt.loc[zt["ROAS"].idxmin()]
        if worst["zone"] != top["zone"]:
            L.append(f"{worst['zone']} pèse sur la rentabilité globale "
                     f"(ROAS {_roas(worst['ROAS'])}) — à surveiller.")
    L.append("")

    # ---- Par levier ----
    L.append("— Performance par levier —")
    ct = analytics.aggregate_by(current, "campaign_type")
    cprev = (analytics.aggregate_by(prev_df, "campaign_type")
             if prev_df is not None else None)
    cprev_rev = (cprev.set_index("campaign_type")["revenue"].to_dict()
                 if cprev is not None and not cprev.empty else {})
    for _, r in ct.iterrows():
        dd = _pct_change(r["revenue"], cprev_rev.get(r["campaign_type"]))
        L.append(f"  • {r['campaign_type']} : Coût {_eur(r['cost'])} · CA "
                 f"{_eur(r['revenue'])}{_delta(dd) if has_comp else ''} · ROAS "
                 f"{_roas(r['ROAS'])}")
    if not ct.empty:
        best = ct.loc[ct["ROAS"].idxmax()]
        worst = ct.loc[ct["ROAS"].idxmin()]
        L.append("")
        L.append(f"{best['campaign_type']} est le levier le plus rentable "
                 f"(ROAS {_roas(best['ROAS'])}).")
        if worst["campaign_type"] != best["campaign_type"]:
            L.append(f"{worst['campaign_type']} est le moins rentable "
                     f"(ROAS {_roas(worst['ROAS'])}) — à prioriser dans les "
                     "optimisations.")
    L.append("")

    # ---- Recommandations ----
    recos = analytics.build_recommendations(current, prev_df)
    if recos:
        L.append("— Recommandations / optimisations —")
        for rc in recos:
            L.append(f"  • {rc['action']} — {rc['rationale']}")
        L.append("")

    # ---- Clôture ----
    L.append("Je reste dispo pour en échanger, on en reparle au prochain point.")
    L.append("")
    L.append("Belle journée,")
    return "\n".join(L)
