"""Génération d'un rapport PDF client (façon synthèse) à partir des données.

Utilise reportlab (polices intégrées, encodage WinAnsi → le symbole € et les
accents sont rendus correctement, sans police externe à embarquer).
Le PDF reprend la charte « Stormy morning » et ne contient que les chiffres
issus des fichiers importés.
"""

from __future__ import annotations

import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core import analytics

# Palette
PRIMARY = colors.HexColor("#384959")
ACCENT = colors.HexColor("#6A89A7")
LIGHT = colors.HexColor("#E7F0FE")
ROWALT = colors.HexColor("#F4F8FD")
TEXT = colors.HexColor("#384959")
POS = colors.HexColor("#2E7D5B")
NEG = colors.HexColor("#B4534B")


def _eur(v):
    return f"{v:,.0f}".replace(",", " ") + " €"


def _cpc(v):
    s = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", " ")
    return f"{s} €"


def _int(v):
    return f"{v:,.0f}".replace(",", " ")


def _roas(v):
    return f"{v:.2f}x".replace(".", ",")


def _pct(v):
    return f"{v * 100:.2f}".replace(".", ",") + " %"


def _fmt(label, v):
    if label == "CPC":
        return _cpc(v)
    if label in ("Coût", "Revenus", "Panier Moyen"):
        return _eur(v)
    if label == "ROAS":
        return _roas(v)
    if label in ("Taux de conversion", "CR"):
        return _pct(v)
    return _int(v)


def _delta(d):
    if d is None:
        return ""
    return f" ({d:+.0f}%)"


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("SeaBrand", parent=ss["Normal"], fontName="Helvetica-Bold",
                          fontSize=16, textColor=PRIMARY))
    ss.add(ParagraphStyle("SeaH1", parent=ss["Normal"], fontName="Helvetica-Bold",
                          fontSize=15, textColor=PRIMARY, spaceBefore=14,
                          spaceAfter=6))
    ss.add(ParagraphStyle("SeaMeta", parent=ss["Normal"], fontSize=9,
                          textColor=ACCENT))
    ss.add(ParagraphStyle("SeaBody", parent=ss["Normal"], fontSize=9.5,
                          textColor=TEXT, leading=13))
    ss.add(ParagraphStyle("SeaHead", parent=ss["Normal"], fontSize=8,
                          fontName="Helvetica-Bold", textColor=colors.white,
                          leading=10))
    ss.add(ParagraphStyle("SeaBullet", parent=ss["Normal"], fontSize=9.5,
                          textColor=TEXT, leading=13, leftIndent=8, spaceAfter=3))
    return ss


def _kpi_table(kpis, prev, S):
    order = ["Coût", "Clics", "CPC", "Conversions", "Revenus",
             "Taux de conversion", "Panier Moyen", "ROAS"]
    header = [Paragraph(f"<b>{k}</b>", S["SeaHead"]) for k in order]
    values = []
    for k in order:
        d = None
        if prev and prev.get(k):
            d = (kpis[k] - prev[k]) / prev[k] * 100 if prev[k] else None
        values.append(Paragraph(_fmt(k, kpis[k]) + _delta(d), S["SeaBody"]))
    t = Table([header, values], colWidths=[None] * len(order))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6E0EC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _comparison_table(table_df, dim_label, S):
    cols = [dim_label] + [lbl for lbl, _ in analytics.TABLE_METRICS]
    head = [Paragraph(c, S["SeaHead"]) for c in cols]
    data = [head]
    dim_col = table_df.columns[0]
    fmts = {"Coût": _eur, "Clics": _int, "Conversions": _int, "Revenus": _eur,
            "CPC": _cpc, "ROAS": _roas, "Panier Moyen": _eur, "CR": _pct}
    for _, r in table_df.iterrows():
        row = [Paragraph(str(r[dim_col]), S["SeaBody"])]
        for lbl, key in analytics.TABLE_METRICS:
            val = fmts[lbl](r[key])
            d = r.get(f"{key}_delta")
            row.append(Paragraph(val + _delta(d if d is not None else None), S["SeaBody"]))
        data.append(row)
    t = Table(data, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D6E0EC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
    # Ligne Total général en gras
    style.append(("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), LIGHT))
    style.append(("FONTNAME", (0, len(data) - 1), (-1, len(data) - 1),
                  "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t


def build_pdf(current, prev_df, period_label, comparison,
              brand="ANALYSE SEA", title="Rapport de performance SEA") -> bytes:
    """Construit le rapport PDF et renvoie les octets."""
    S = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm,
                            bottomMargin=16 * mm, leftMargin=15 * mm,
                            rightMargin=15 * mm, title=title)
    el = []
    el.append(Paragraph(brand, S["SeaBrand"]))
    el.append(Paragraph(f"<b>{title}</b>", S["SeaH1"]))
    meta = f"Période : {period_label}"
    if comparison and comparison != "Aucune":
        meta += f" &nbsp;·&nbsp; Comparaison : {comparison.lower()}"
    meta += f" &nbsp;·&nbsp; Édité le {dt.date.today():%d/%m/%Y}"
    el.append(Paragraph(meta, S["SeaMeta"]))
    el.append(Spacer(1, 8))

    kpis = analytics.compute_kpis(current)
    prev_kpis = analytics.compute_kpis(prev_df) if prev_df is not None else None
    el.append(Paragraph("Indicateurs clés", S["SeaH1"]))
    el.append(_kpi_table(kpis, prev_kpis, S))

    el.append(Paragraph("Performance par type de campagne", S["SeaH1"]))
    el.append(_comparison_table(
        analytics.comparison_table(current, prev_df, "campaign_type"),
        "Type de campagne", S))

    el.append(Paragraph("Performance par zone", S["SeaH1"]))
    el.append(_comparison_table(
        analytics.comparison_table(current, prev_df, "zone"), "Zone", S))

    insights = analytics.build_insights(current, prev_df)
    if insights:
        el.append(Paragraph("Synthèse", S["SeaH1"]))
        for ins in insights:
            el.append(Paragraph(f"• <b>{ins['title']}</b> — {ins['detail']}",
                                S["SeaBullet"]))

    recos = analytics.build_recommendations(current, prev_df)
    if recos:
        el.append(Paragraph("Recommandations", S["SeaH1"]))
        for rc in recos:
            el.append(Paragraph(
                f"• <b>[{rc['priority'].upper()}] {rc['action']}</b> — "
                f"{rc['rationale']}", S["SeaBullet"]))

    doc.build(el)
    return buf.getvalue()
