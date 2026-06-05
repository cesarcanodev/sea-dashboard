"""Génération automatique du compte-rendu / email client (texte).

Produit un texte français prêt à copier-coller dans un email, rempli avec les
vrais chiffres de la période : KPIs (avec WoW), performance par zone et par
levier, constats et recommandations. La narration est pilotée par les données ;
l'utilisateur peut ensuite éditer le texte avant envoi.
"""

from __future__ import annotations

import re

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
def _f1(v):
    return f"{v:.1f}".replace(".", ",")


def _table(headers, rows):
    """Petit tableau aligné en texte (colonnes séparées par 2 espaces)."""
    cols = list(zip(*([headers] + rows)))
    w = [max(len(str(c)) for c in col) for col in cols]
    def fmt(r):
        return "  ".join(str(c).ljust(w[i]) for i, c in enumerate(r))
    out = [fmt(headers), "  ".join("-" * x for x in w)]
    out += [fmt(r) for r in rows]
    return "\n".join(out)


def build_email(current, prev_df, period_label, comparison,
                recipient: str = "", signature: str = "César") -> str:
    """Compte-rendu client, rédigé dans le ton de César (« Hello… », « Au
    global… », recaps, focus zones & leviers, « Belle journée »)."""
    k = analytics.compute_kpis(current)
    kp = analytics.compute_kpis(prev_df) if prev_df is not None else None
    d = {key: _pct_change(k[key], kp[key]) for key in k} if kp \
        else {key: None for key in k}
    has_comp = kp is not None and comparison != "Aucune"
    lp = "LY" if comparison == "Année précédente" else "LP"
    plural = bool(re.search(r"\bet\b|,", recipient)) if recipient else False

    L = []
    L.append(f"Hello {recipient}," if recipient else "Hello,")
    L.append("")
    L.append("J'espère que vous allez bien. \U0001F642" if plural
             else "J'espère que tu vas bien !")
    L.append("")
    intro = f"Petit point perf SEA sur la période {period_label}"
    if has_comp:
        intro += f" vs {lp}"
    L.append(intro + " avant notre point.")
    L.append("")

    # --- Au global ---
    g = f"Au global, le ROAS Server Side ressort à {_roas(k['ROAS'])}"
    if has_comp and d["ROAS"] is not None:
        g += f" (vs {_roas(kp['ROAS'])})"
    L.append(g + ".")

    if has_comp:
        cd = d["Clics"]
        if cd is None:
            traf = "Le trafic reste stable"
        elif abs(cd) < 3:
            traf = "Le trafic reste quasi iso"
        else:
            soft = "légère " if abs(cd) < 10 else ""
            traf = f"Le trafic est en {soft}{'hausse' if cd > 0 else 'baisse'} ({cd:+.0f} %)"
        if d["CPC"] is not None:
            if d["CPC"] < 0:
                traf += f" et nous avons réduit nos CPC de {abs(d['CPC']):.0f} % au global."
            else:
                traf += f", avec des CPC en hausse de {d['CPC']:.0f} % au global."
        else:
            traf += "."
        L.append(traf)

        cv = d["Conversions"]
        if cv is not None and cv < 0:
            strong = "forte " if abs(cv) >= 25 else ""
            L.append(f"Malgré ce trafic, on observe une {strong}baisse des "
                     f"conversions ({cv:+.0f} %), le trafic ayant été moins "
                     f"qualifié vs {lp}.")
        elif cv is not None and cv > 0:
            L.append(f"Bon signe côté qualité : les conversions progressent de "
                     f"{cv:.0f} %.")
    L.append("À noter, des remontées de conversion à venir de l'ordre de "
             "10 à 20 %.")
    L.append("")

    # --- Recap perfs globales ---
    L.append("Recap perfs globales")
    specs = [("Coût", "Coût", _eur), ("Clics", "Clics", _int),
             ("CPC moyen", "CPC", _cpc), ("Conversions SS", "Conversions", _int),
             ("CA Server Side", "Revenus", _eur),
             ("Panier moyen", "Panier Moyen", _eur),
             ("Taux de conv. (CR)", "Taux de conversion", _pct),
             ("ROAS Server Side", "ROAS", _roas)]
    if has_comp:
        hdr = ["KPI", "Préc.", "Période", "WoW"]
        rows = [[lbl, fmt(kp[key]), fmt(k[key]),
                 (f"{d[key]:+.0f} %" if d[key] is not None else "—")]
                for lbl, key, fmt in specs]
    else:
        hdr = ["KPI", "Période"]
        rows = [[lbl, fmt(k[key])] for lbl, key, fmt in specs]
    L.append(_table(hdr, rows))
    L.append("")

    # --- Recap perfs par région (zones) ---
    zt = analytics.aggregate_by(current, "zone")
    if not zt.empty:
        L.append("Recap perfs par région")
        zhdr = ["Zone", "Coût", "Clics", "CPC", "Conv. SS", "CA SS", "ROAS SS"]
        zrows = [[r["zone"], _eur(r["cost"]), _int(r["clicks"]), _cpc(r["CPC"]),
                  _f1(r["conversions"]), _eur(r["revenue"]), _roas(r["ROAS"])]
                 for _, r in zt.iterrows()]
        zrows.append(["Total", _eur(k["Coût"]), _int(k["Clics"]), _cpc(k["CPC"]),
                      _f1(k["Conversions"]), _eur(k["Revenus"]), _roas(k["ROAS"])])
        L.append(_table(zhdr, zrows))
        L.append("")

    # --- Focus par zones & leviers ---
    L.append("Focus par zones & leviers")
    total_rev = k["Revenus"]
    if not zt.empty:
        top = zt.iloc[0]
        L.append(f"{top['zone']}, notre meilleure région, "
                 f"{_share(top['revenue'], total_rev):.0f} % du CA et la plus "
                 f"rentable à {_roas(top['ROAS'])}.")
        wz = zt.loc[zt["ROAS"].idxmin()]
        if wz["zone"] != top["zone"]:
            L.append(f"{wz['zone']}, la zone qui pèse sur notre ROAS global "
                     f"(ROAS {_roas(wz['ROAS'])}), on la surveille de près.")
    ct = analytics.aggregate_by(current, "campaign_type")
    if not ct.empty:
        best = ct.loc[ct["ROAS"].idxmax()]
        L.append(f"{best['campaign_type']}, notre levier le plus rentable "
                 f"(ROAS {_roas(best['ROAS'])}, {_share(best['revenue'], total_rev):.0f} % "
                 f"du CA), on garde le cap.")
        worst = ct.loc[ct["ROAS"].idxmin()]
        if worst["campaign_type"] != best["campaign_type"]:
            L.append(f"{worst['campaign_type']}, le levier le moins rentable "
                     f"(ROAS {_roas(worst['ROAS'])}), on le priorise dans les "
                     f"optimisations.")
    L.append("")

    # --- Optimisations + clôture ---
    recos = analytics.build_recommendations(current, prev_df)
    if recos:
        actions = " ; ".join(r["action"] for r in recos[:3])
        L.append(f"Côté optimisations cette semaine : {actions}.")
        L.append("")
    if plural:
        L.append("Je reste dispo si vous avez la moindre question !")
    else:
        L.append("De ton côté, comment se situe le ratio dépense vs CA ? "
                 "On en reparle pendant le weekly !")
    L.append("")
    L.append("Belle journée,")
    L.append(signature)
    return "\n".join(L)
