"""Génération automatique du compte-rendu / email client (texte).

Produit un texte français prêt à copier-coller dans un email, rempli avec les
vrais chiffres de la période : KPIs (avec WoW), performance par zone et par
levier, constats et recommandations. La narration est pilotée par les données ;
l'utilisateur peut ensuite éditer le texte avant envoi.
"""

from __future__ import annotations

import re
from html import escape

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


def _week_label(dmin, dmax) -> str:
    """« S22 (25 au 31) » à partir des bornes de dates de la période."""
    try:
        wk = int(dmin.isocalendar()[1])
    except Exception:
        return f"{dmin.day} au {dmax.day}"
    return f"S{wk} ({dmin.day} au {dmax.day})"


def _agg_delta(current, prev_df, dim):
    """Agrège par dimension + variation %Δ du CA et ROAS précédent par valeur."""
    cur = analytics.aggregate_by(current, dim)
    prev = analytics.aggregate_by(prev_df, dim) if prev_df is not None else None
    pidx = (prev.set_index(dim) if prev is not None and not prev.empty else None)
    meta = {}
    for _, r in cur.iterrows():
        name = r[dim]
        ca_d = None
        if pidx is not None and name in pidx.index:
            ca_d = _pct_change(r["revenue"], pidx.loc[name]["revenue"])
        meta[name] = ca_d
    return cur, meta


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def _top_sub(current, prev_df, filter_col, filter_val, sub_col):
    """Dans le sous-ensemble {filter_col == filter_val}, renvoie le 1er sous-
    segment par CA : (nom, ROAS, %Δ CA vs comparaison) — pour « la France porte
    la zone », « Shopping concentré sur l'APAC », etc."""
    sub = current[current[filter_col] == filter_val]
    agg = analytics.aggregate_by(sub, sub_col)
    if agg.empty:
        return None
    top = agg.iloc[0]
    ca_d = None
    if prev_df is not None:
        psub = prev_df[prev_df[filter_col] == filter_val]
        pagg = analytics.aggregate_by(psub, sub_col)
        if not pagg.empty:
            pix = pagg.set_index(sub_col)
            if top[sub_col] in pix.index:
                ca_d = _pct_change(top["revenue"], pix.loc[top[sub_col]]["revenue"])
    return top[sub_col], top["ROAS"], ca_d


def _soldes_share(current, filter_col, filter_val) -> float:
    """Part de budget en campagnes Sales/Soldes dans un segment (0 à 1)."""
    sub = current[current[filter_col] == filter_val]
    tot = sub["cost"].sum()
    if not tot or "campaign_name" not in sub.columns:
        return 0.0
    m = analytics._name_has(sub["campaign_name"], analytics._SALES_TOKENS)
    return float(sub.loc[m.values, "cost"].sum()) / float(tot)


def _build_blocks(current, prev_df, period_label, comparison,
                  recipient: str = "", signature: str = "César",
                  trend: str = "") -> list:
    """Construit le compte-rendu sous forme de blocs (un seul contenu, deux
    rendus possibles : texte brut ou HTML mis en forme).

    Types de blocs :
        ("text", str)                       — paragraphe
        ("section", titre, headers, rows, total_last)  — titre + tableau
        ("lines", titre, [str, ...])        — titre + lignes (focus)
    """
    k = analytics.compute_kpis(current)
    kp = analytics.compute_kpis(prev_df) if prev_df is not None else None
    d = {key: _pct_change(k[key], kp[key]) for key in k} if kp \
        else {key: None for key in k}
    has_comp = kp is not None and comparison != "Aucune"
    lp = "LY" if comparison == "Année précédente" else "LP"
    plural = bool(re.search(r"\bet\b|,", recipient)) if recipient else False
    total_rev = k["Revenus"]

    B = []
    B.append(("text", f"Hello {recipient}," if recipient else "Hello,"))
    B.append(("text", "J'espère que vous allez bien. \U0001F642" if plural
              else "J'espère que tu vas bien !"))
    intro = "Petit point perf SEA sur la semaine écoulée"
    if has_comp:
        intro += f" vs {lp}"
    B.append(("text", intro + " avant notre weekly."))

    # --- Paragraphe « Au global » ---
    glob = []
    g = f"Au global, le ROAS Server Side ressort à {_roas(k['ROAS'])}"
    if has_comp and d["ROAS"] is not None:
        g += f" (vs {_roas(kp['ROAS'])})"
    glob.append(g + ".")
    if has_comp:
        cd = d["Clics"]
        if cd is None or abs(cd) < 3:
            traf = "Le trafic reste quasi iso"
        else:
            soft = "légère " if abs(cd) < 10 else ""
            traf = (f"Le trafic est en {soft}"
                    f"{'hausse' if cd > 0 else 'baisse'} ({cd:+.0f} %)")
        if d["CPC"] is not None and d["CPC"] < 0:
            traf += f" et nous avons réduit nos CPC de {abs(d['CPC']):.0f} % au global."
        elif d["CPC"] is not None:
            traf += f", avec des CPC en hausse de {d['CPC']:.0f} % au global."
        else:
            traf += "."
        glob.append(traf)
        cv = d["Conversions"]
        if cv is not None and cv < 0:
            pref = ("Malgré ce trafic en légère baisse, " if (cd is not None and cd < 0)
                    else "Malgré ce trafic, ")
            strong = "forte " if abs(cv) >= 25 else ""
            qual = ("nettement moins qualifié"
                    if (d["Taux de conversion"] or 0) <= -20 else "moins qualifié")
            glob.append(f"{pref}on observe une {strong}baisse des conversions, "
                        f"le trafic ayant été {qual} vs {lp}.")
        elif cv is not None and cv > 0:
            glob.append(f"Bon signe côté qualité, les conversions progressent de "
                        f"{cv:.0f} %.")
    sc = analytics.sales_context(current)
    if sc and sc["share"] >= 0.20:
        glob.append(f"Plusieurs marchés sont en soldes ({sc['share']*100:.0f} % du "
                    "budget), ce qui pèse mécaniquement sur le panier et le ROAS.")
    glob.append("À noter, des remontées de conversion à venir de l'ordre de "
                "10 à 20 %.")
    B.append(("text", " ".join(glob)))

    # --- Recap perfs globales ---
    specs = [("Coût", "Coût", _eur), ("Clics", "Clics", _int),
             ("CPC moyen", "CPC", _cpc), ("Conversions SS", "Conversions", _int),
             ("CA Server Side", "Revenus", _eur),
             ("Panier moyen", "Panier Moyen", _eur),
             ("Taux de conv. (CR)", "Taux de conversion", _pct),
             ("ROAS Server Side", "ROAS", _roas)]
    cur_lbl = _week_label(current["date"].min(), current["date"].max())
    if has_comp and prev_df is not None and not prev_df.empty:
        prev_lbl = _week_label(prev_df["date"].min(), prev_df["date"].max())
        hdr = ["KPI global", prev_lbl, cur_lbl, "WoW"]
        rows = [[lbl, fmt(kp[key]), fmt(k[key]),
                 (f"{d[key]:+.0f} %" if d[key] is not None else "—")]
                for lbl, key, fmt in specs]
    else:
        hdr = ["KPI global", cur_lbl]
        rows = [[lbl, fmt(k[key])] for lbl, key, fmt in specs]
    B.append(("section", "Recap perfs globales", hdr, rows, False))

    # --- Recap perfs par région ---
    zt, zmeta = _agg_delta(current, prev_df, "zone")
    if not zt.empty:
        zhdr = ["Zone", "Coût", "Clics", "CPC", "Conv. SS", "CA SS", "ROAS SS"]
        zrows = [[r["zone"], _eur(r["cost"]), _int(r["clicks"]), _cpc(r["CPC"]),
                  _f1(r["conversions"]), _eur(r["revenue"]), _roas(r["ROAS"])]
                 for _, r in zt.iterrows()]
        zrows.append(["Total", _eur(k["Coût"]), _int(k["Clics"]), _cpc(k["CPC"]),
                      _f1(k["Conversions"]), _eur(k["Revenus"]), _roas(k["ROAS"])])
        B.append(("section", "Recap perfs par région", zhdr, zrows, True))

    # --- Focus par zones & leviers ---
    focus = []
    best_zone = worst_zone = best_lev = worst_lev = None
    if not zt.empty:
        top = zt.iloc[0]
        best_zone = top["zone"]
        line = (f"{top['zone']}, notre meilleure région, "
                f"{_share(top['revenue'], total_rev):.0f} % du CA")
        line += (f" et la plus rentable à {_roas(top['ROAS'])}"
                 if top["ROAS"] == zt["ROAS"].max() else f" (ROAS {_roas(top['ROAS'])})")
        if zmeta.get(top["zone"]) is not None:
            line += f", CA {zmeta[top['zone']]:+.0f} %"
        focus.append(line + ".")
        sub = _top_sub(current, prev_df, "zone", top["zone"], "country")
        if sub and sub[0]:
            cname, croas, cad = sub
            if cad is not None and cad > 0:
                focus.append(f"{cname} porte la zone, en progression "
                             f"(ROAS {_roas(croas)}, CA {cad:+.0f} %).")
            elif cad is not None:
                focus.append(f"{cname} porte la zone (ROAS {_roas(croas)}, "
                             f"CA {cad:+.0f} %).")
            else:
                focus.append(f"{cname} porte la zone (ROAS {_roas(croas)}).")
        wz = zt.loc[zt["ROAS"].idxmin()]
        worst_zone = wz["zone"]
        if wz["zone"] != top["zone"]:
            seg = (f"{wz['zone']}, la région qui pèse sur notre ROAS global "
                   f"(ROAS {_roas(wz['ROAS'])}")
            if zmeta.get(wz["zone"]) is not None:
                seg += f", CA {zmeta[wz['zone']]:+.0f} %"
            seg += ")"
            if _soldes_share(current, "zone", wz["zone"]) >= 0.30:
                seg += ", effet des soldes en cours"
            focus.append(seg + ".")

    ct, cmeta = _agg_delta(current, prev_df, "campaign_type")
    if not ct.empty:
        best = ct.loc[ct["ROAS"].idxmax()]
        best_lev = best["campaign_type"]
        seg = (f"{best['campaign_type']}, notre levier le plus rentable "
               f"(ROAS {_roas(best['ROAS'])}")
        if cmeta.get(best_lev) is not None:
            seg += f", CA {cmeta[best_lev]:+.0f} %"
        seg += ")"
        cs = _share(best["cost"], k["Coût"])
        rs = _share(best["revenue"], total_rev)
        if rs >= cs + 4:
            seg += (f", split dépense/CA très favorable ({cs:.0f} % du coût pour "
                    f"{rs:.0f} % du CA)")
        focus.append(seg + ".")
        brand = ct[ct["campaign_type"].map(analytics._is_brand_label)]
        if not brand.empty:
            bb = brand.iloc[0]
            if bb["campaign_type"] != best_lev:
                focus.append(f"{bb['campaign_type']}, notre épine dorsale "
                             f"({_share(bb['revenue'], total_rev):.0f} % du CA), "
                             f"ROAS {_roas(bb['ROAS'])} — on le priorise dans les "
                             "optimisations.")
        paid = ct[ct["cost"] > 0]
        if not paid.empty:
            worst = paid.loc[paid["ROAS"].idxmin()]
            worst_lev = worst["campaign_type"]
            if worst_lev != best_lev:
                seg = (f"{worst_lev}, le levier le moins rentable "
                       f"(ROAS {_roas(worst['ROAS'])})")
                wsub = _top_sub(current, None, "campaign_type", worst_lev, "zone")
                if wsub and wsub[0]:
                    seg += f", concentré sur {wsub[0]}"
                    if _soldes_share(current, "campaign_type", worst_lev) >= 0.30:
                        seg += " en soldes"
                if best_lev:
                    seg += f", on réalloue progressivement son budget vers {best_lev}"
                focus.append(seg + ".")
    if focus:
        B.append(("lines", "Focus par zones & leviers", focus))

    # --- Synthèse des optimisations ---
    recos = analytics.build_recommendations(current, prev_df)
    opt = "Côté optimisations cette semaine, "
    if recos:
        opt += " et ".join(_lower_first(r["action"]) for r in recos[:2]) + ". "
    forts = " et ".join(x for x in (best_zone, best_lev) if x)
    faibles = " et ".join(x for x in (worst_zone, worst_lev) if x)
    if forts and faibles:
        opt += (f"Le point fort de la semaine reste {forts} qui maintiennent une "
                f"belle rentabilité ; le point faible vient de {faibles} qui "
                "tirent le ROAS global vers le bas.")
    B.append(("text", opt.strip()))

    # --- Clôture ---
    trend_txt = f" des {trend.strip()}" if trend and trend.strip() else ""
    if plural:
        B.append(("text", "Je reste dispo si vous avez la moindre question !"))
    else:
        B.append(("text", "De ton côté, comment se situe le ratio dépense vs CA, "
                  f"on reste bien dans le trend{trend_txt} ?"))
    B.append(("text", "On en reparle pendant le weekly !"))
    B.append(("text", "Belle journée,\n" + signature))
    return B


def _render_text(blocks) -> str:
    out = []
    for b in blocks:
        if b[0] == "text":
            out.append(b[1])
        elif b[0] == "section":
            out.append(b[1] + "\n" + _table(b[2], b[3]))
        elif b[0] == "lines":
            out.append(b[1] + "\n" + "\n".join(b[2]))
    return "\n\n".join(out)


# Coloration des variations : vert si positif, rouge si négatif.
_DELTA_RE = re.compile(r"^[+-]\d")


def _html_inline(s: str) -> str:
    return escape(s).replace("\n", "<br>")


def _html_table(headers, rows, total_last=False) -> str:
    P, POS, NEG = "#384959", "#2E7D5B", "#B4534B"
    th = ""
    for i, h in enumerate(headers):
        align = "left" if i == 0 else "right"
        th += (f'<th style="background:{P};color:#FFFFFF;padding:7px 11px;'
               f'text-align:{align};font-weight:700;border:1px solid {P};">'
               f'{escape(str(h))}</th>')
    body = ""
    for ri, row in enumerate(rows):
        is_total = total_last and ri == len(rows) - 1
        tds = ""
        for ci, c in enumerate(row):
            c = str(c)
            align = "left" if ci == 0 else "right"
            style = (f"padding:6px 11px;border:1px solid #E3EAF3;text-align:{align};"
                     "color:#384959;")
            if _DELTA_RE.match(c) and not c.startswith("+0 "):
                style += f"color:{POS};font-weight:600;" if c[0] == "+" \
                    else f"color:{NEG};font-weight:600;"
            if ci == 0 or is_total:
                style += "font-weight:700;"
            if is_total:
                style += "background:#E7F0FE;border-top:2px solid #384959;"
            tds += f'<td style="{style}">{escape(c)}</td>'
        body += f"<tr>{tds}</tr>"
    return (f'<table style="border-collapse:collapse;font-size:13px;'
            f'font-family:Arial,Helvetica,sans-serif;margin:6px 0 16px;">'
            f"<tr>{th}</tr>{body}</table>")


def _render_html(blocks) -> str:
    parts = []
    for b in blocks:
        if b[0] == "text":
            parts.append(f'<p style="margin:0 0 12px;">{_html_inline(b[1])}</p>')
        elif b[0] == "section":
            parts.append(f'<p style="margin:16px 0 4px;font-weight:700;'
                         f'color:#384959;">{escape(b[1])}</p>')
            parts.append(_html_table(b[2], b[3], b[4]))
        elif b[0] == "lines":
            parts.append(f'<p style="margin:16px 0 4px;font-weight:700;'
                         f'color:#384959;">{escape(b[1])}</p>')
            parts.append('<p style="margin:0 0 12px;">'
                         + "<br>".join(_html_inline(x) for x in b[2]) + "</p>")
    return ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
            f'color:#384959;line-height:1.5;">{"".join(parts)}</div>')


def build_email(current, prev_df, period_label, comparison,
                recipient: str = "", signature: str = "César",
                trend: str = "") -> str:
    """Compte-rendu client en **texte brut** (édition / copier-coller simple)."""
    return _render_text(_build_blocks(current, prev_df, period_label, comparison,
                                      recipient, signature, trend))


def build_email_html(current, prev_df, period_label, comparison,
                     recipient: str = "", signature: str = "César",
                     trend: str = "") -> str:
    """Même compte-rendu en **HTML mis en forme** : tableaux bordés, total et
    en-têtes en gras, variations WoW en vert (positif) / rouge (négatif).
    À coller dans Gmail (la mise en forme est conservée)."""
    return _render_html(_build_blocks(current, prev_df, period_label, comparison,
                                      recipient, signature, trend))
