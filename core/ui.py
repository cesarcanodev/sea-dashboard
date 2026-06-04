"""Composants d'interface partagés entre les pages du dashboard SEA.

Centralise : thème, CSS, formatage, scorecards, bandeaux, tableaux « Looker »,
graphiques Plotly, et le chargement de données + contrôles de la sidebar.
Les deux pages (Performance, Analyse) importent depuis ce module pour garder
une charte visuelle homogène.
"""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

from core import analytics
from core.normalizer import detect_mapping, normalize
from core.readers import ReaderError, read_file

# --------------------------------------------------------------------------- #
# Thème — palette neutre, sobre et professionnelle (re-brandable ici)
# --------------------------------------------------------------------------- #
# Palette « Stormy morning » : #6A89A7 #BDDDFC #88BDF2 #384959
THEME = {
    "brand": "ANALYSE SEA",
    "title": "Vue d'ensemble des performances",
    "primary": "#384959",          # bleu ardoise foncé (bandeaux, en-têtes, barres)
    "primary_dark": "#2C3A47",     # variante plus sombre
    "primary_light": "#BDDDFC",    # bleu très clair
    "accent": "#6A89A7",           # bleu-gris moyen (lignes)
    "secondary": "#6A89A7",
    "secondary_light": "#BDDDFC",  # séries « période précédente »
    "positive": "#2E7D5B",         # vert sobre (variations positives)
    "negative": "#B4534B",         # rouge brique sobre (variations négatives)
    "grid": "#E8EEF5",
    "text": "#384959",             # couleur de police principale
    "muted": "#6A89A7",            # texte secondaire
}
# Dégradé de la palette pour les répartitions (donuts, segmentations)
CATEGORY_COLORS = ["#384959", "#6A89A7", "#88BDF2", "#BDDDFC", "#52708C", "#A9CDEB"]


def inject_theme() -> None:
    """Injecte le CSS de la charte. Idempotent (sans danger si appelé 2×)."""
    _inject_css()


def _inject_css() -> None:
    T = THEME
    st.markdown(
        f"""
        <style>
        /* Fond blanc + police lisible partout */
        .stApp {{background:#FFFFFF;}}
        .block-container {{padding-top: 1.4rem; max-width: 1400px; color:{T['text']};}}
        .sc, .card, .tile, table.looker {{color:{T['text']};}}
        .header-band {{
            display:flex; align-items:center; justify-content:space-between;
            border-bottom:3px solid {T['primary']}; padding:4px 4px 14px;
            margin-bottom:14px;
        }}
        .header-logo {{
            font-size:18px; font-weight:800; letter-spacing:2px;
            color:{T['primary']}; border:2px solid {T['primary']};
            padding:8px 16px; border-radius:6px;
        }}
        .header-title {{font-size:21px; font-weight:700; color:{T['text']};}}
        .header-date {{font-size:14px; color:{T['muted']}; font-weight:600;}}
        .section-band {{
            background:{T['primary']}; color:#FFFFFF; text-align:center;
            padding:9px; font-weight:700; text-transform:uppercase;
            letter-spacing:1.5px; border-radius:4px; margin:24px 0 12px;
            font-size:13px;
        }}
        /* Scorecards — hauteur uniforme (libellés sur 1 ou 2 lignes alignés) */
        .sc {{border:1px solid #E3EAF3; border-radius:10px; padding:14px 10px;
            text-align:center; background:#FFFFFF; height:100%;
            display:flex; flex-direction:column; justify-content:flex-start;
            box-shadow:0 1px 2px rgba(30,58,138,.05);}}
        .sc-label {{font-size:11px; color:{T['muted']}; text-transform:uppercase;
            letter-spacing:.5px; margin-bottom:6px; line-height:1.25;
            min-height:28px; display:flex; align-items:center;
            justify-content:center;}}
        .sc-value {{font-size:23px; font-weight:700; color:{T['text']};
            line-height:1.2; margin-top:auto;}}
        .sc-delta {{font-size:12px; font-weight:600; margin-top:3px;}}
        .sc-pos {{color:{T['positive']};}} .sc-neg {{color:{T['negative']};}}
        .sc-flat {{color:{T['muted']};}}
        /* Tuiles par région */
        .tile {{border:1px solid #E3EAF3; border-left:5px solid {T['primary']};
            border-radius:10px; padding:14px 16px; background:#FFFFFF; height:100%;
            box-shadow:0 1px 2px rgba(30,58,138,.05);}}
        .tile-name {{font-size:13px; font-weight:700; color:{T['primary_dark']};
            text-transform:uppercase; letter-spacing:.5px;}}
        .tile-main {{font-size:24px; font-weight:800; color:{T['text']};
            margin:4px 0 2px;}}
        .tile-sub {{font-size:12px; color:{T['muted']};}}
        .tile-delta {{font-size:12px; font-weight:600; margin-left:6px;}}
        /* Tableaux */
        table.looker {{border-collapse:collapse; width:100%; font-size:13px;}}
        table.looker thead th {{background:{T['primary']}; color:#FFFFFF;
            text-align:right; padding:8px 10px; font-weight:600; white-space:nowrap;}}
        table.looker thead th:first-child {{text-align:left;}}
        table.looker tbody td {{padding:7px 10px; text-align:right; color:{T['text']};
            border-bottom:1px solid #EDF1F7; white-space:nowrap;}}
        table.looker tbody td:first-child {{text-align:left; font-weight:600;}}
        table.looker tbody tr:nth-child(even) {{background:#F6F9FE;}}
        table.looker tr.grand-total td {{font-weight:800;
            border-top:2px solid {T['primary']}; background:#E7F0FE;}}
        .delta {{font-size:11px; margin-left:6px; color:{T['muted']};}}
        .d-pos {{color:{T['positive']};}} .d-neg {{color:{T['negative']};}}
        /* Cartes insight / reco */
        .card {{border:1px solid #E3EAF3; border-left-width:5px; border-radius:8px;
            padding:12px 16px; margin-bottom:10px; background:#FFFFFF;
            box-shadow:0 1px 2px rgba(30,58,138,.05);}}
        .card-title {{font-weight:700; font-size:15px; margin-bottom:3px;
            color:{T['text']};}}
        .card-detail {{font-size:13px; color:{T['muted']};}}
        .lv-good {{border-left-color:{T['positive']};}}
        .lv-warn {{border-left-color:#D97706;}}
        .lv-bad {{border-left-color:{T['negative']};}}
        .lv-info {{border-left-color:{T['primary']};}}
        .badge {{display:inline-block; font-size:11px; font-weight:700;
            padding:2px 9px; border-radius:12px; color:#FFFFFF; margin-right:8px;}}
        .bg-haute {{background:{T['negative']};}}
        .bg-moyenne {{background:#D97706;}}
        .bg-basse {{background:{T['primary_light']}; color:{T['primary_dark']};}}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Chargement des données (cache) + sidebar partagée
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _read_one(file_bytes: bytes, file_name: str):
    """Lit + normalise un fichier. Renvoie (df_normalisé, colonnes_originales)."""
    buf = io.BytesIO(file_bytes)
    buf.name = file_name
    raw = read_file(buf)
    return normalize(raw), list(raw.columns)


def sidebar_data_source() -> pd.DataFrame | None:
    """Rend l'uploader dans la sidebar et renvoie le DataFrame normalisé.

    Le dashboard ne lit que les fichiers réellement importés par l'utilisateur :
    aucune donnée n'est inventée ni transformée (seuls le nettoyage de format et
    le mapping de colonnes sont appliqués). Le résultat est mémorisé dans
    st.session_state pour être partagé entre toutes les pages.
    """
    st.sidebar.header("📥 Sources de données")
    uploaded = st.sidebar.file_uploader(
        "Importer vos fichiers (CSV, Excel, PDF)",
        type=["csv", "xlsx", "xls", "pdf"], accept_multiple_files=True,
    )

    # Chargement automatique dès qu'un (nouveau) fichier est importé ; le bouton
    # permet en plus de forcer un rechargement.
    sig = tuple((f.name, f.size) for f in uploaded) if uploaded else None
    reload_clicked = st.sidebar.button(
        "📊 Charger les performances", width="stretch",
        disabled=not uploaded,
        help="Lit les fichiers importés et affiche le dashboard.")

    if uploaded and (reload_clicked or sig != st.session_state.get("loaded_sig")):
        if reload_clicked:
            # Vide le cache pour relire avec le code le plus récent
            # (utile après une mise à jour de l'app).
            st.cache_data.clear()
        frames, empties, detected = [], [], {}
        for f in uploaded:
            try:
                norm, cols = _read_one(f.getvalue(), f.name)
                detected[f.name] = list(cols)
                if norm.empty:
                    empties.append((f.name, cols))
                else:
                    frames.append(norm)
            except (ReaderError, ValueError) as exc:
                st.sidebar.error(f"« {f.name} » : {exc}")
            except Exception as exc:
                st.sidebar.error(f"« {f.name} » : erreur inattendue ({exc})")
        st.session_state["loaded_columns"] = detected
        if frames:
            st.session_state["data"] = pd.concat(frames, ignore_index=True)
            st.session_state["loaded_sig"] = sig
        for name, cols in empties:
            _diagnose_empty(name, cols)

    df = st.session_state.get("data")
    if df is not None and not df.empty:
        st.sidebar.success(
            f"✅ {len(df):,} lignes chargées · "
            f"{df['date'].min():%d/%m/%Y} → {df['date'].max():%d/%m/%Y}"
            .replace(",", " "))
        if st.sidebar.button("🗑️ Réinitialiser", width="stretch"):
            for k in ("data", "loaded_sig"):
                st.session_state.pop(k, None)
            st.rerun()
    return df


def _diagnose_empty(name: str, cols: list) -> None:
    """Explique pourquoi un fichier n'a donné aucune ligne exploitable."""
    mapping = detect_mapping(cols)
    recognised = {k: v for k, v in mapping.items() if v}
    st.sidebar.error(f"« {name} » : aucune ligne exploitable.")
    st.sidebar.caption("Colonnes trouvées : " + ", ".join(map(str, cols)))
    if recognised:
        st.sidebar.caption(
            "Reconnues : " + ", ".join(f"{k} → {v}" for k, v in recognised.items()))
        if "date" in recognised.values():
            st.sidebar.caption("⚠️ Colonnes OK mais dates non interprétées : "
                               "vérifiez le format de la colonne date.")
        else:
            st.sidebar.caption("⚠️ Aucune colonne « date » reconnue (obligatoire).")
    else:
        st.sidebar.caption("⚠️ Aucun en-tête reconnu. Renommez vos colonnes "
                           "(Date, Pays, Type de campagne, Clics, Coût, "
                           "Conversions, Revenus) ou envoyez-moi vos intitulés.")


def sidebar_filters(df: pd.DataFrame):
    """Sélecteurs période + comparaison, partagés entre toutes les pages.

    Les widgets utilisent une clé stable (`flt_period`, `flt_comparison`) : leur
    valeur persiste dans st.session_state, donc le même réglage s'applique à tous
    les onglets. Renvoie (start, end, comparison).
    """
    min_d, max_d = df["date"].min().date(), df["date"].max().date()
    st.sidebar.header("🗓️ Période")
    # Pas de bornes min/max : liberté totale de sélection (les périodes sans
    # donnée sont gérées proprement en aval).
    rng = st.sidebar.date_input("Plage de dates", value=(min_d, max_d),
                                key="flt_period")
    st.sidebar.caption(f"Données disponibles : {min_d:%d/%m/%Y} → {max_d:%d/%m/%Y}")
    if not isinstance(rng, (tuple, list)) or len(rng) != 2:
        st.sidebar.warning("Sélectionnez une date de début ET de fin.")
        return None
    start, end = rng
    if start > end:
        st.sidebar.error("Début postérieur à la fin.")
        return None
    st.sidebar.header("⚙️ Comparaison")
    comp = st.sidebar.selectbox(
        "Mode", ["Aucune", "Période précédente", "Année précédente"],
        key="flt_comparison")
    return start, end, comp


def pdf_export_button(current, prev_df, period_label, comparison) -> None:
    """Bouton sidebar : génère le rapport PDF puis propose son téléchargement."""
    from core import export

    st.sidebar.header("📄 Export")
    if st.sidebar.button("Générer le rapport PDF", width="stretch"):
        try:
            st.session_state["pdf_bytes"] = export.build_pdf(
                current, prev_df, period_label, comparison)
            st.session_state["pdf_name"] = (
                f"rapport_sea_{dt.date.today():%Y%m%d}.pdf")
        except Exception as exc:
            st.sidebar.error(f"Échec de la génération PDF : {exc}")
    if st.session_state.get("pdf_bytes"):
        st.sidebar.download_button(
            "⬇️ Télécharger le PDF", data=st.session_state["pdf_bytes"],
            file_name=st.session_state.get("pdf_name", "rapport_sea.pdf"),
            mime="application/pdf", width="stretch")


def resolve_periods(df, start, end, comparison):
    """Renvoie (current_df, previous_df_or_None, previous_range_or_None)."""
    current = analytics.slice_period(df, start, end)
    prev_df, prev_range = None, analytics.previous_period(start, end, comparison)
    if prev_range is not None:
        prev_df = analytics.slice_period(df, *prev_range)
        if prev_df.empty:
            prev_df = None
    return current, prev_df, prev_range


# --------------------------------------------------------------------------- #
# Formatage
# --------------------------------------------------------------------------- #
def fmt_eur(v: float) -> str:
    """Montant arrondi à l'euro : « 4 083 € »."""
    return f"{v:,.0f}".replace(",", " ") + " €"


def fmt_cpc(v: float) -> str:
    """CPC : 2 décimales (montant < 1 €) → « 0,34 € »."""
    s = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", " ")
    return f"{s} €"


def fmt_int(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def fmt_roas(v: float) -> str:
    return f"{v:.2f}x".replace(".", ",")


def fmt_pct(v: float) -> str:
    """v est un ratio (0.0033) → « 0,33 % »."""
    return f"{v * 100:.2f}".replace(".", ",") + " %"


def fmt_metric(label: str, v: float) -> str:
    if label == "CPC":
        return fmt_cpc(v)
    if label in ("Coût", "Revenus", "Panier Moyen"):
        return fmt_eur(v)
    if label == "ROAS":
        return fmt_roas(v)
    if label in ("Taux de conversion", "CR"):
        return fmt_pct(v)
    return fmt_int(v)


def _delta_pct(cur: float, prev: float | None):
    if prev in (None, 0, 0.0) or pd.isna(prev):
        return None
    return (cur - prev) / prev * 100


def _delta_span(delta, big=True):
    cls_pre = "sc-delta" if big else "delta"
    if delta is None or pd.isna(delta):
        return f'<span class="{cls_pre} {"sc-flat" if big else ""}">—</span>'
    arrow = "▲" if delta >= 0 else "▼"
    good = delta >= 0
    cls = ("sc-pos" if good else "sc-neg") if big else ("d-pos" if good else "d-neg")
    return f'<span class="{cls_pre} {cls}">{arrow} {delta:+.0f}%</span>'


# --------------------------------------------------------------------------- #
# Composants
# --------------------------------------------------------------------------- #
def header_band(date_label: str, title: str | None = None) -> None:
    st.markdown(
        f"""<div class="header-band">
            <div class="header-logo">{THEME['brand']}</div>
            <div class="header-title">{title or THEME['title']}</div>
            <div class="header-date">📅 {date_label}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def section_band(text: str) -> None:
    st.markdown(f'<div class="section-band">{text}</div>', unsafe_allow_html=True)


def scorecard_row(kpis: dict, prev: dict | None, items: list[str]) -> None:
    cols = st.columns(len(items))
    for col, key in zip(cols, items):
        d = _delta_pct(kpis[key], prev[key]) if prev else None
        with col:
            st.markdown(
                f'<div class="sc"><div class="sc-label">{key}</div>'
                f'<div class="sc-value">{fmt_metric(key, kpis[key])}</div>'
                f"{_delta_span(d)}</div>",
                unsafe_allow_html=True,
            )


def breakdown_tiles(current, prev_df, dimension: str) -> None:
    """Une tuile par valeur de la dimension (région ou pays) : Revenus en
    grand, ROAS + Coût en sous-titre, et %Δ des revenus vs comparaison."""
    agg = analytics.aggregate_by(current, dimension)
    if agg.empty:
        return
    prev_agg = (analytics.aggregate_by(prev_df, dimension)
                if prev_df is not None else None)
    prev_rev = (prev_agg.set_index(dimension)["revenue"].to_dict()
                if prev_agg is not None and not prev_agg.empty else {})

    cols = st.columns(len(agg))
    for col, (_, r) in zip(cols, agg.iterrows()):
        d = _delta_pct(r["revenue"], prev_rev.get(r[dimension]))
        delta = _delta_span(d, big=False) if d is not None else ""
        with col:
            st.markdown(
                f'<div class="tile"><div class="tile-name">{r[dimension]}</div>'
                f'<div class="tile-main">{fmt_eur(r["revenue"])} '
                f'<span class="tile-delta">{delta}</span></div>'
                f'<div class="tile-sub">ROAS {fmt_roas(r["ROAS"])} · '
                f'Coût {fmt_eur(r["cost"])} · {fmt_int(r["conversions"])} conv.'
                f"</div></div>",
                unsafe_allow_html=True,
            )


def looker_table(table: pd.DataFrame, dim_label: str) -> None:
    fmts = {"Coût": fmt_eur, "Clics": fmt_int, "Conversions": fmt_int,
            "Revenus": fmt_eur, "CPC": fmt_cpc, "ROAS": fmt_roas,
            "Panier Moyen": fmt_eur, "CR": fmt_pct}
    dim_col = table.columns[0]
    head = f"<th>{dim_label}</th>" + "".join(
        f"<th>{lbl}</th>" for lbl, _ in analytics.TABLE_METRICS)
    body = ""
    for _, r in table.iterrows():
        is_total = str(r[dim_col]) == "Total général"
        row_cls = ' class="grand-total"' if is_total else ""
        cells = f"<td>{r[dim_col]}</td>"
        for lbl, key in analytics.TABLE_METRICS:
            val = fmts[lbl](r[key]) if pd.notna(r[key]) else "—"
            delta_span = _delta_span(r.get(f"{key}_delta"), big=False)
            cells += f"<td>{val} {delta_span}</td>"
        body += f"<tr{row_cls}>{cells}</tr>"
    st.markdown(
        f'<table class="looker"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table>",
        unsafe_allow_html=True,
    )


def _fmt_for(label):
    """Renvoie le formateur d'affichage d'une métrique."""
    if label in ("Coût", "Revenus", "Panier Moyen"):
        return fmt_eur
    if label == "CPC":
        return fmt_cpc
    if label == "ROAS":
        return fmt_roas
    if label == "CR":
        return fmt_pct
    return fmt_int


def _cell(r, lbl, key):
    """Cellule : valeur formatée + petit Δ% coloré (façon Looker)."""
    val = _fmt_for(lbl)(r[key]) if pd.notna(r[key]) else "—"
    sort_v = float(r[key]) if pd.notna(r[key]) else -1e18
    d = r.get(f"{key}_delta")
    delta = ""
    if d is not None and not pd.isna(d):
        cls = "dp" if d >= 0 else "dn"
        arrow = "▲" if d >= 0 else "▼"
        delta = f'<span class="{cls}">{arrow}{d:+.0f}%</span>'
    return f'<td data-sort="{sort_v}">{val} {delta}</td>'


def interactive_table(table: pd.DataFrame, dim_label: str) -> None:
    """Tableau « Looker » clair, total en pied, triable au clic sur l'en-tête
    (1 clic = croissant, 2 clics = décroissant). Rendu en HTML/JS maison pour
    une charte 100 % maîtrisée (toujours clair, quel que soit le thème)."""
    dim_col = table.columns[0]
    body = table[table[dim_col] != "Total général"]
    total = table[table[dim_col] == "Total général"]

    headers = [dim_label] + [lbl for lbl, _ in analytics.TABLE_METRICS]
    th = "".join(
        f'<th onclick="sortT({i})">{h}<span class="arr" id="a{i}"></span></th>'
        for i, h in enumerate(headers))

    rows_html = ""
    for _, r in body.iterrows():
        cells = f'<td data-sort="{r[dim_col]}">{r[dim_col]}</td>'
        for lbl, key in analytics.TABLE_METRICS:
            cells += _cell(r, lbl, key)
        rows_html += f"<tr>{cells}</tr>"

    foot = ""
    if not total.empty:
        r = total.iloc[0]
        cells = f"<td>{r[dim_col]}</td>"
        for lbl, key in analytics.TABLE_METRICS:
            val = _fmt_for(lbl)(r[key]) if pd.notna(r[key]) else "—"
            cells += f"<td>{val}</td>"
        foot = f'<tr class="gt">{cells}</tr>'

    P, POS, NEG = THEME["primary"], THEME["positive"], THEME["negative"]
    html = f"""
    <style>
      *{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         box-sizing:border-box;}}
      body{{margin:0;background:#FFFFFF;}}
      table{{border-collapse:collapse;width:100%;font-size:13px;color:#384959;}}
      thead th{{background:{P};color:#FFFFFF;padding:9px 10px;text-align:right;
        cursor:pointer;white-space:nowrap;user-select:none;position:sticky;top:0;}}
      thead th:first-child{{text-align:left;}}
      thead th:hover{{background:#2C3A47;}}
      tbody td{{padding:7px 10px;text-align:right;border-bottom:1px solid #EDF1F7;
        white-space:nowrap;}}
      tbody td:first-child{{text-align:left;font-weight:600;}}
      tbody tr:nth-child(even){{background:#F6F9FE;}}
      tbody tr:hover{{background:#E7F0FE;}}
      tfoot td{{padding:9px 10px;text-align:right;font-weight:800;
        background:#E7F0FE;border-top:2px solid {P};}}
      tfoot td:first-child{{text-align:left;}}
      .dp{{color:{POS};font-size:11px;margin-left:5px;}}
      .dn{{color:{NEG};font-size:11px;margin-left:5px;}}
      .arr{{font-size:10px;margin-left:4px;color:#BDDDFC;}}
    </style>
    <table id="t">
      <thead><tr>{th}</tr></thead>
      <tbody>{rows_html}</tbody>
      <tfoot>{foot}</tfoot>
    </table>
    <script>
      var dir={{}};
      function sortT(n){{
        var t=document.getElementById('t'),tb=t.tBodies[0];
        var rows=Array.prototype.slice.call(tb.rows);
        dir[n]=dir[n]==='asc'?'desc':'asc';var d=dir[n]==='asc'?1:-1;
        rows.sort(function(a,b){{
          var x=a.cells[n].getAttribute('data-sort'),
              y=b.cells[n].getAttribute('data-sort');
          var xn=parseFloat(x),yn=parseFloat(y);
          if(!isNaN(xn)&&!isNaN(yn))return (xn-yn)*d;
          return (''+x).localeCompare(''+y)*d;
        }});
        rows.forEach(function(r){{tb.appendChild(r);}});
        var arrs=document.getElementsByClassName('arr');
        for(var i=0;i<arrs.length;i++)arrs[i].textContent='';
        document.getElementById('a'+n).textContent=dir[n]==='asc'?'▲':'▼';
      }}
    </script>
    """
    height = 56 + len(body) * 35 + (40 if foot else 0)
    components.html(html, height=height, scrolling=True)


def insight_card(level: str, title: str, detail: str) -> None:
    st.markdown(
        f'<div class="card lv-{level}"><div class="card-title">{title}</div>'
        f'<div class="card-detail">{detail}</div></div>',
        unsafe_allow_html=True,
    )


def reco_card(priority: str, action: str, rationale: str) -> None:
    st.markdown(
        f'<div class="card lv-info"><div class="card-title">'
        f'<span class="badge bg-{priority}">{priority.upper()}</span>{action}</div>'
        f'<div class="card-detail">{rationale}</div></div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Graphiques
# --------------------------------------------------------------------------- #
def _layout(fig, title="", height=330):
    fig.update_layout(
        title=title, title_font=dict(size=15, color=THEME["text"]),
        font=dict(color=THEME["text"], size=12),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(color=THEME["text"])),
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white", paper_bgcolor="white", height=height,
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color=THEME["text"]))
    fig.update_yaxes(gridcolor=THEME["grid"], zeroline=False,
                     tickfont=dict(color=THEME["text"]))
    return fig


def donut(agg, dim, value_col, title):
    # On exclut « Autre » / total des donuts (uniquement les vrais leviers).
    a = agg[~agg[dim].astype(str).isin(["Autre", "Total général", "", "nan"])]
    if a.empty:
        a = agg
    fig = go.Figure(go.Pie(
        labels=a[dim], values=a[value_col], hole=0.62,
        marker=dict(colors=CATEGORY_COLORS, line=dict(color="#FFFFFF", width=2)),
        textinfo="percent", textposition="outside",
        outsidetextfont=dict(size=11, color=THEME["text"]), sort=False))
    fig.update_layout(
        title=title, title_font=dict(size=14, color=THEME["text"]), title_x=0.5,
        font=dict(color=THEME["text"], size=11),
        paper_bgcolor="white", plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.08,
                    font=dict(size=11, color=THEME["text"])),
        margin=dict(l=10, r=10, t=44, b=10), height=300)
    return fig


def _aligned(cur_m, prev_m, col):
    labels = [d.strftime("%b %Y") for d in cur_m["period"]]
    cur_vals = cur_m[col].tolist()
    prev_vals = None
    if prev_m is not None and not prev_m.empty:
        pv = prev_m[col].tolist()
        prev_vals = (pv + [None] * len(labels))[: len(labels)]
    return labels, cur_vals, prev_vals


def combo_bar_line(cur_m, prev_m, bar_col, line_col, bar_name, line_name, title):
    labels, bar_vals, bar_prev = _aligned(cur_m, prev_m, bar_col)
    _, line_vals, line_prev = _aligned(cur_m, prev_m, line_col)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=labels, y=bar_vals, name=bar_name,
                  marker_color=THEME["primary"]), secondary_y=False)
    if bar_prev and any(v is not None for v in bar_prev):
        fig.add_trace(go.Bar(x=labels, y=bar_prev, name=f"{bar_name} (N-1)",
                      marker_color=THEME["primary_light"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=labels, y=line_vals, name=line_name,
                  mode="lines+markers", line=dict(color=THEME["accent"], width=3)),
                  secondary_y=True)
    if line_prev and any(v is not None for v in line_prev):
        fig.add_trace(go.Scatter(x=labels, y=line_prev, name=f"{line_name} (N-1)",
                      mode="lines+markers",
                      line=dict(color=THEME["secondary_light"], width=2, dash="dot")),
                      secondary_y=True)
    _layout(fig, title)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text=bar_name, secondary_y=False)
    fig.update_yaxes(title_text=line_name, secondary_y=True)
    return fig


def daily_combo(df, prev_df=None):
    """Vue Globale : clics (barres) + revenus (ligne) par jour, + overlay N-1."""
    d = analytics.daily_series(df)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=d["date"], y=d["clicks"], name="Clics",
                  marker_color=THEME["primary"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=d["date"], y=d["revenue"], name="Revenus",
                  mode="lines", line=dict(color=THEME["accent"], width=3)),
                  secondary_y=True)
    if prev_df is not None and not prev_df.empty:
        dp = analytics.daily_series(prev_df)
        fig.add_trace(go.Scatter(x=d["date"][: len(dp)], y=dp["revenue"],
                      name="Revenus (N-1)", mode="lines",
                      line=dict(color=THEME["secondary_light"], width=2, dash="dot")),
                      secondary_y=True)
    _layout(fig, "Évolution quotidienne — Clics & Revenus")
    fig.update_yaxes(title_text="Clics", secondary_y=False)
    fig.update_yaxes(title_text="Revenus (€)", secondary_y=True)
    return fig


def dimension_combo(df, dimension, label):
    """Vue segmentée : revenus (barres) + ROAS (ligne) par dimension."""
    agg = analytics.aggregate_by(df, dimension)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=agg[dimension], y=agg["revenue"], name="Revenus",
                  marker_color=THEME["primary"]), secondary_y=False)
    fig.add_trace(go.Scatter(x=agg[dimension], y=agg["ROAS"], name="ROAS",
                  mode="lines+markers", line=dict(color=THEME["accent"], width=3)),
                  secondary_y=True)
    _layout(fig, f"Revenus & ROAS — {label}")
    fig.update_yaxes(title_text="Revenus (€)", secondary_y=False)
    fig.update_yaxes(title_text="ROAS", secondary_y=True)
    return fig


def lines(cur_m, prev_m, specs, title):
    """Courbes multiples avec overlay N-1. specs = [(col, name, color)]."""
    fig = go.Figure()
    for col, name, color in specs:
        labels, vals, prev = _aligned(cur_m, prev_m, col)
        fig.add_trace(go.Scatter(x=labels, y=vals, name=name, mode="lines+markers",
                      line=dict(color=color, width=3)))
        if prev and any(v is not None for v in prev):
            fig.add_trace(go.Scatter(x=labels, y=prev, name=f"{name} (N-1)",
                          mode="lines+markers", opacity=0.5,
                          line=dict(color=color, width=2, dash="dot")))
    _layout(fig, title)
    return fig


# Échelle de couleurs bleue (palette « Stormy morning ») pour les heatmaps.
BLUE_SCALE = [[0.0, "#EAF3FB"], [0.5, "#6A89A7"], [1.0, "#384959"]]


def heatmap(pivot_df, title, metric_label, pct=False):
    """Tableau croisé sous forme de heatmap annotée."""
    if pivot_df.empty:
        fig = go.Figure()
        _layout(fig, title, height=360)
        return fig
    z = pivot_df.values
    if metric_label == "ROAS":
        texts = [[f"{v:.2f}x" if pd.notna(v) else "" for v in row] for row in z]
    elif metric_label in ("Coût", "Revenus", "CPC", "Panier Moyen"):
        texts = [[fmt_eur(v) if pd.notna(v) else "" for v in row] for row in z]
    else:
        texts = [[fmt_int(v) if pd.notna(v) else "" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=list(pivot_df.columns), y=list(pivot_df.index),
        colorscale=BLUE_SCALE, text=texts, texttemplate="%{text}",
        textfont=dict(size=12, color=THEME["text"]),
        hoverongaps=False, colorbar=dict(title=metric_label)))
    _layout(fig, title, height=120 + 60 * len(pivot_df.index))
    fig.update_xaxes(side="top")
    return fig


def perf_scatter(agg, dimension, label):
    """Matrice de performance : Coût (x) vs Revenus (y), couleur=ROAS,
    taille=conversions, une bulle par valeur de la dimension."""
    fig = go.Figure()
    if not agg.empty:
        sizeref = 2.0 * max(agg["conversions"].max(), 1) / (45.0 ** 2)
        fig.add_trace(go.Scatter(
            x=agg["cost"], y=agg["revenue"], mode="markers+text",
            text=agg[dimension], textposition="top center",
            textfont=dict(size=10, color=THEME["text"]),
            marker=dict(
                size=agg["conversions"], sizemode="area", sizeref=sizeref,
                sizemin=6, color=agg["ROAS"], colorscale=BLUE_SCALE,
                showscale=True, colorbar=dict(title="ROAS"),
                line=dict(width=1, color="#FFFFFF")),
            customdata=agg[["ROAS", "conversions"]],
            hovertemplate=(f"<b>%{{text}}</b><br>Coût %{{x:,.0f}} €<br>"
                           "Revenus %{y:,.0f} €<br>ROAS %{customdata[0]:.2f}x<br>"
                           "Conversions %{customdata[1]:,.0f}<extra></extra>")))
    _layout(fig, f"Matrice de performance — {label}", height=460)
    fig.update_xaxes(title_text="Coût (€)")
    fig.update_yaxes(title_text="Revenus (€)")
    return fig


def pareto_chart(par, dimension, metric_label):
    """Diagramme de Pareto : barres (contribution) + courbe cumulée."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not par.empty:
        key = analytics.METRIC_KEYS[metric_label]
        fig.add_trace(go.Bar(x=par[dimension], y=par[key], name=metric_label,
                      marker_color=THEME["primary"]), secondary_y=False)
        fig.add_trace(go.Scatter(x=par[dimension], y=par["cumul"], name="Cumul %",
                      mode="lines+markers", line=dict(color=THEME["accent"], width=3)),
                      secondary_y=True)
        fig.add_hline(y=80, line_dash="dot", line_color=THEME["negative"],
                      secondary_y=True)
    _layout(fig, f"Contribution au {metric_label.lower()} (Pareto)", height=380)
    fig.update_yaxes(title_text=metric_label, secondary_y=False)
    fig.update_yaxes(title_text="Cumul %", range=[0, 105], secondary_y=True)
    return fig
