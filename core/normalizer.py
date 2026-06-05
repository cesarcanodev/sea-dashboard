"""Normalisation des données SEA vers un schéma canonique.

Schéma canonique cible :
    date, country, region, campaign_type, clicks, cost, conversions, revenue

Principes :
    * On NE stocke jamais de KPI dérivé (CPC, ROAS, AOV). Seules les mesures
      brutes (clics, coût, conversions, revenus) sont conservées.
    * Les en-têtes FR et EN sont reconnus via ``COLUMN_ALIASES``.
    * Les nombres au format français (espaces insécables, virgule décimale,
      symbole €) sont nettoyés avant conversion.
"""

from __future__ import annotations

import re
import warnings

import numpy as np
import pandas as pd

from core import clients

# --------------------------------------------------------------------------- #
# Schéma canonique
# --------------------------------------------------------------------------- #
CANONICAL_COLUMNS = [
    "date",
    "country",
    "region",
    "zone",
    "campaign_type",
    "clicks",
    "cost",
    "conversions",
    "revenue",
]

MEASURE_COLUMNS = ["clicks", "cost", "conversions", "revenue"]
TEXT_COLUMNS = ["country", "campaign_type"]


# --------------------------------------------------------------------------- #
# Mapping des en-têtes (FR + EN) → schéma canonique
# --------------------------------------------------------------------------- #
# Les clés sont normalisées (minuscule, sans accent, sans ponctuation) avant
# comparaison via ``_canon_key``.
COLUMN_ALIASES = {
    # date
    "date": "date",
    "jour": "date",
    "day": "date",
    "week": "date",
    "semaine": "date",
    "mois": "date",
    "month": "date",
    "periode": "date",
    "date de debut": "date",
    "start date": "date",
    # country
    "pays": "country",
    "country": "country",
    "marche": "country",  # « marché »
    # campaign_type
    "type": "campaign_type",
    "typologie": "campaign_type",
    "type de campagne": "campaign_type",
    "campaign": "campaign_type",
    "campaign type": "campaign_type",
    "campagne": "campaign_type",
    # clicks
    "clics": "clicks",
    "clic": "clicks",
    "clicks": "clicks",
    "click": "clicks",
    # cost
    "cout": "cost",
    "couts": "cost",
    "cost": "cost",
    "spend": "cost",
    "depense": "cost",
    "depenses": "cost",
    # conversions (y compris variantes « Server Side » / SS)
    "achats": "conversions",
    "achat": "conversions",
    "conversions": "conversions",
    "conversion": "conversions",
    "purchases": "conversions",
    "purchase": "conversions",
    "ventes": "conversions",
    "conversions server side": "conversions",
    "conversion server side": "conversions",
    "conv server side": "conversions",
    "ss conversions": "conversions",
    "conversions ss": "conversions",
    "conv ss": "conversions",
    "conversions serveur": "conversions",
    # revenue (y compris variantes « Server Side » / SS)
    "revenus": "revenue",
    "revenu": "revenue",
    "revenue": "revenue",
    "ca": "revenue",
    "chiffre daffaires": "revenue",
    "conv value": "revenue",
    "conv_value": "revenue",
    "conv value server side": "revenue",
    "valeur conversion": "revenue",
    "valeur de conversion": "revenue",
    "valeur des conversions": "revenue",
    "revenus server side": "revenue",
    "revenue server side": "revenue",
    "revenus ss": "revenue",
    "ss revenue": "revenue",
    "revenue ss": "revenue",
    "valeur de conversion server side": "revenue",
    "conv val server side": "revenue",
}


# --------------------------------------------------------------------------- #
# Mapping pays → région
# --------------------------------------------------------------------------- #
COUNTRY_TO_REGION = {
    # Amérique
    "USA": "Amérique",
    "États-Unis": "Amérique",
    "Etats-Unis": "Amérique",
    "United States": "Amérique",
    "Canada": "Amérique",
    "Brésil": "Amérique",
    "Bresil": "Amérique",
    "Brazil": "Amérique",
    "Mexique": "Amérique",
    "Argentine": "Amérique",
    # Europe
    "France": "Europe",
    "Allemagne": "Europe",
    "Germany": "Europe",
    "Espagne": "Europe",
    "Spain": "Europe",
    "Italie": "Europe",
    "Royaume-Uni": "Europe",
    "Royaume Uni": "Europe",
    "United Kingdom": "Europe",
    "Pays-Bas": "Europe",
    "Belgique": "Europe",
    "Suisse": "Europe", "Portugal": "Europe", "Irlande": "Europe",
    "Autriche": "Europe", "Pologne": "Europe", "Danemark": "Europe",
    "Suède": "Europe", "Finlande": "Europe", "Norvège": "Europe",
    "Tchéquie": "Europe", "Slovaquie": "Europe", "Slovénie": "Europe",
    "Croatie": "Europe", "Hongrie": "Europe", "Roumanie": "Europe",
    "Bulgarie": "Europe", "Grèce": "Europe", "Luxembourg": "Europe",
    "Lituanie": "Europe", "Lettonie": "Europe", "Estonie": "Europe",
    "Islande": "Europe", "Monaco": "Europe", "Chypre": "Europe",
    "Malte": "Europe", "Serbie": "Europe", "Ukraine": "Europe",
    "Turquie": "Europe",
    # Asie
    "Japon": "Asie",
    "Japan": "Asie",
    "Chine": "Asie",
    "China": "Asie",
    "Inde": "Asie",
    "India": "Asie",
    "Corée Du Sud": "Asie",
    "Coree Du Sud": "Asie",
    "Singapour": "Asie",
    "Indonésie": "Asie",
    "Hong Kong": "Asie",
    "Malaisie": "Asie",
    "Pan-Asie": "Asie",
    # Océanie
    "Australie": "Océanie",
    # Regroupements
    "Multi-pays": "Multi-pays",
    "International": "International",
    "Monde": "International",
}

# Les zones de reporting sont définies par client dans core/clients.py.


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #
def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Transforme un DataFrame brut en DataFrame au schéma canonique.

    Étapes :
        1. Renommage des colonnes reconnues vers le schéma canonique.
        2. Création des colonnes manquantes avec des valeurs neutres.
        3. Parsing des dates (format français, dayfirst).
        4. Nettoyage des nombres au format français.
        5. Déduction de ``region`` depuis ``country``.
        6. Nettoyage des chaînes (strip / title).
    """
    if df is None or df.empty:
        raise ValueError("Aucune donnée à normaliser (DataFrame vide).")

    df = df.copy()

    # 1. Sélection des colonnes : alias exacts (priorité Server Side) puis repli
    #    flou pour les mesures manquantes.
    chosen = resolve_columns(df.columns)
    df = pd.DataFrame({canon: df[src].values for canon, src in chosen.items()})

    # 2. Colonnes manquantes → valeurs neutres
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            if col in MEASURE_COLUMNS:
                df[col] = 0
            else:
                df[col] = ""

    # 3. Dates : on tente le format français (dayfirst), avec repli automatique
    #    sur l'inférence standard si la majorité échoue (ex. dates ISO ou
    #    anglaises type « Jan 1, 2026 » issues d'exports Looker/Google Ads).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        if len(parsed) and parsed.isna().mean() > 0.5:
            fallback = pd.to_datetime(df["date"], errors="coerce")
            if fallback.notna().sum() > parsed.notna().sum():
                parsed = fallback
    df["date"] = parsed.dt.normalize()

    # 4. Nombres (format français)
    for col in MEASURE_COLUMNS:
        df[col] = _clean_numeric(df[col])

    # 4b. Détection du client (d'après les noms de campagne) → règles propres :
    #     tokens de type + regroupements de zones. Le libellé de campagne ne
    #     contient QUE le type (pas le pays).
    raw_campaign = df["campaign_type"].astype(str)
    cfg = clients.config_for(raw_campaign.tolist())
    df.attrs["client"] = cfg["name"]
    parsed = raw_campaign.apply(lambda x: parse_campaign(x, cfg["types"]))
    df["campaign_type"] = [
        _campaign_label(orig, t) for orig, (t, _) in zip(raw_campaign, parsed)]
    parsed_country = [c for (_, c) in parsed]
    country_blank = df["country"].astype(str).str.strip().isin(
        ["", "nan", "None"])
    df["country"] = [
        pc if blank and pc else orig
        for orig, blank, pc in zip(df["country"].astype(str),
                                   country_blank, parsed_country)]

    # 4c. Lignes parasites : on retire les lignes de total/vides « -- » de
    #     l'export (uniquement si une vraie colonne campagne existait).
    if "campaign_type" in chosen:
        junk = raw_campaign.str.strip().str.lower().isin(_JUNK_CAMPAIGN)
        df = df[~junk.values].reset_index(drop=True)

    # 6a. Nettoyage texte : pays en Title Case ; campaign_type garde sa casse
    #     (le label « PMax FR » est déjà propre).
    df["country"] = _clean_text(df["country"])
    df["campaign_type"] = df["campaign_type"].astype(str).str.strip()

    # 5. Région + zone de reporting déduites du pays (zone selon le client)
    df["region"] = _derive_region(df["country"])
    df["zone"] = _derive_zone(df["country"], cfg["zones"])

    # On retire les lignes sans date valide (inexploitables).
    df = df[df["date"].notna()].reset_index(drop=True)

    # Ordre canonique + on conserve le client détecté (attrs survit au slicing).
    out = df[CANONICAL_COLUMNS].copy()
    out.attrs["client"] = cfg["name"]
    return out


# --------------------------------------------------------------------------- #
# Parsing des noms de campagne → type normalisé + code pays
# --------------------------------------------------------------------------- #
# Codes pays (2 et 3 lettres) + cas spéciaux → pays. Étendre selon vos marchés.
COUNTRY_CODE_TO_COUNTRY = {
    # 2 lettres
    "FR": "France", "DE": "Allemagne", "ES": "Espagne", "IT": "Italie",
    "UK": "Royaume-Uni", "GB": "Royaume-Uni", "BE": "Belgique",
    "NL": "Pays-Bas", "CH": "Suisse", "PT": "Portugal", "IE": "Irlande",
    "US": "États-Unis", "CA": "Canada", "BR": "Brésil", "MX": "Mexique",
    "JP": "Japon", "CN": "Chine", "IN": "Inde", "KR": "Corée Du Sud",
    "SG": "Singapour", "AU": "Australie", "HK": "Hong Kong", "MY": "Malaisie",
    # 3 lettres (ISO-3)
    "FRA": "France", "DEU": "Allemagne", "ESP": "Espagne", "ITA": "Italie",
    "GBR": "Royaume-Uni", "BEL": "Belgique", "NLD": "Pays-Bas", "CHE": "Suisse",
    "PRT": "Portugal", "IRL": "Irlande", "USA": "États-Unis", "CAN": "Canada",
    "BRA": "Brésil", "MEX": "Mexique", "JPN": "Japon", "CHN": "Chine",
    "IND": "Inde", "KOR": "Corée Du Sud", "SGP": "Singapour", "AUS": "Australie",
    "HKG": "Hong Kong", "MYS": "Malaisie",
    # 2 lettres — autres marchés européens
    "AT": "Autriche", "PL": "Pologne", "DK": "Danemark", "SE": "Suède",
    "SW": "Suède", "FI": "Finlande", "NO": "Norvège", "CZ": "Tchéquie",
    "SK": "Slovaquie", "SI": "Slovénie", "HR": "Croatie", "HU": "Hongrie",
    "RO": "Roumanie", "BG": "Bulgarie", "GR": "Grèce", "LU": "Luxembourg",
    "LT": "Lituanie", "LV": "Lettonie", "EE": "Estonie", "IS": "Islande",
    "MC": "Monaco", "CY": "Chypre", "MT": "Malte", "RS": "Serbie",
    "UA": "Ukraine", "TR": "Turquie",
    # cas spéciaux / regroupements
    "MULTI": "Multi-pays", "PAN-ASIA": "Pan-Asie", "PANASIA": "Pan-Asie",
    "EU": "Europe", "EUR": "Europe", "WW": "Monde", "INT": "International",
    "EN": "International",
}

_JUNK_CAMPAIGN = {"", "nan", "none", "--", "-", "n/a", "na", "total", "totals"}


def parse_campaign(raw, type_patterns=None):
    """Depuis un nom de campagne, renvoie (libellé_type|None, pays|None).

    Le type est **affiché littéralement** selon la nomenclature du client
    (« Brand Other », « Pure Brand », « Branded », « Brex », « DSA », « PMax »…).

    ``type_patterns`` : liste ordonnée de (motif, libellé). Un motif multi-mots
    (« pure brand ») est cherché en sous-chaîne ; un motif d'un seul mot
    (« pla ») doit être un **token exact** — ce qui évite les faux positifs
    (ex. « pla » présent dans « display »). L'ordre fixe la priorité.

    Le pays est déduit du 1ᵉʳ code reconnu (un token « SK/EN » donne « SK »).
    """
    if type_patterns is None:
        type_patterns = clients.DEFAULT_TYPES
    key = _canon_key(raw)          # minuscule, sans accent, espaces simples
    toks = set(key.split())
    type_label = None
    for pat, label in type_patterns:
        if (pat in key) if (" " in pat) else (pat in toks):
            type_label = label
            break

    country = None
    for t in re.split(r"[_\s|:]+", str(raw)):
        for sub in re.split(r"[/-]", t):
            u = re.sub(r"[^A-Za-z]", "", sub).upper()
            if u in COUNTRY_CODE_TO_COUNTRY:
                country = COUNTRY_CODE_TO_COUNTRY[u]
                break
        if country:
            break
    return type_label, country


def _campaign_label(original, type_label) -> str:
    """Libellé de campagne = type pur (sans pays). Vides/« -- » → « Autre »."""
    if type_label:
        return type_label
    o = str(original).strip()
    if o.lower() in _JUNK_CAMPAIGN:
        return "Autre"
    return o.title()


def detect_mapping(columns) -> dict:
    """Pour une liste d'en-têtes, renvoie {en-tête original : champ canonique
    ou None}. Sert au diagnostic d'import (colonnes reconnues / ignorées)."""
    return {str(c): COLUMN_ALIASES.get(_canon_key(c)) for c in columns}


# Heuristiques de repli (matching flou) quand l'alias exact échoue.
_FUZZY = {
    "revenue": (("valeur", "value", "revenu", "revenue", "montant", "sales",
                 "chiffre", "turnover", "ca"),
                ("rate", "taux", "cvr", "cpc", "cpa", "roas", "ratio", "/",
                 "moyen", "par clic", "cost")),
    "conversions": (("conversion", "conversions", "conv", "achat", "purchase",
                     "vente", "lead", "acquisition"),
                    ("value", "valeur", "val", "rate", "taux", "cvr", "cout",
                     "cost", "%", "par ", "/")),
    "cost": (("cost", "cout", "spend", "depense", "budget", "investiss"),
             ("per ", "par ", "cpc", "cpa", "cpm", "/")),
    "clicks": (("clic", "click"), ("rate", "taux", "ctr", "%", "par ", "/")),
}


def _fuzzy_find(columns, used, field):
    """Cherche une colonne plausible pour un champ via mots-clés (repli).

    Les motifs courts (≤ 2 lettres, ex. « ca ») sont testés en mot entier pour
    éviter les faux positifs ; les autres en sous-chaîne."""
    pos, neg = _FUZZY[field]
    cands = [c for c in columns if c not in used]

    def ok(c):
        k = _canon_key(c)
        if any(n in k for n in neg):
            return False
        toks = set(k.split())
        return any((p in toks) if len(p) <= 2 else (p in k) for p in pos)

    m = [c for c in cands if ok(c)]
    if not m:
        return None
    ss = [c for c in m if "server" in _canon_key(c)]
    return (ss or m)[0]


def resolve_columns(columns) -> dict:
    """Choisit la meilleure colonne source pour chaque champ canonique.

    1) Alias exacts (priorité aux variantes « Server Side »).
    2) Repli flou par mots-clés pour les mesures encore manquantes.
    Renvoie {champ_canonique : en-tête original}.
    """
    groups: dict[str, list] = {}
    for col in columns:
        canon = COLUMN_ALIASES.get(_canon_key(col))
        if canon:
            groups.setdefault(canon, []).append(col)
    chosen = {}
    for canon, srcs in groups.items():
        ss = [s for s in srcs if "server" in _canon_key(s)]
        chosen[canon] = ss[0] if ss else srcs[0]
    used = set(chosen.values())
    for field in ("revenue", "conversions", "cost", "clicks"):
        if field not in chosen:
            cand = _fuzzy_find(columns, used, field)
            if cand:
                chosen[field] = cand
                used.add(cand)
    return chosen


def _recognised_count(columns) -> int:
    """Nombre d'en-têtes reconnus comme champs canoniques."""
    return sum(1 for v in detect_mapping(columns).values() if v)


def promote_header(df: pd.DataFrame) -> pd.DataFrame:
    """Détecte et promeut la vraie ligne d'en-tête.

    Beaucoup d'exports (Google Ads, Looker…) commencent par une ligne de titre
    et/ou une plage de dates : la 1ʳᵉ ligne lue n'est donc pas la bonne (colonnes
    « Unnamed: N »). On scanne les premières lignes pour trouver celle qui
    contient le plus d'en-têtes reconnus, et on l'utilise comme en-tête.
    """
    if df is None or df.empty:
        return df
    # En-tête actuel déjà valable ? on ne touche à rien.
    if _recognised_count(df.columns) >= 2:
        return df
    best_i, best = None, 1  # il faut au moins 2 colonnes reconnues
    for i in range(min(len(df), 20)):
        score = _recognised_count(list(df.iloc[i].values))
        if score > best:
            best, best_i = score, i
    if best_i is None:
        return df
    new_cols = [str(c).strip() for c in df.iloc[best_i].values]
    out = df.iloc[best_i + 1:].copy()
    out.columns = new_cols
    return out.loc[:, ~out.columns.duplicated()].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Helpers internes
# --------------------------------------------------------------------------- #
_ACCENTS = str.maketrans("àâäéèêëïîôöùûüç", "aaaeeeeiioouuuc")


def _canon_key(label: str) -> str:
    """Normalise un en-tête pour la comparaison : minuscule, sans accent,
    ponctuation réduite à des espaces simples."""
    s = str(label).strip().lower().translate(_ACCENTS)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _clean_numeric(series: pd.Series) -> pd.Series:
    """Convertit une colonne en nombres en gerant LES DEUX formats :
    francais (1 234,56) ET anglais/US (1,234.56). Le separateur decimal est
    deduit par valeur (le dernier separateur rencontre est le decimal)."""
    return series.astype(str).map(_parse_number).astype(float)


def _parse_number(x) -> float:
    """Parse un nombre quel que soit le format (FR ou US). 0.0 si vide."""
    x = re.sub(r"[\u20ac$%\s]", "", str(x))
    if x in ("", "-", "--", "nan", "None", "NaN", "N/A", "n/a"):
        return 0.0
    neg = x.startswith("-")
    x = x.lstrip("+-")
    has_c, has_d = "," in x, "." in x
    if has_c and has_d:
        if x.rfind(",") > x.rfind("."):
            x = x.replace(".", "").replace(",", ".")
        else:
            x = x.replace(",", "")
    elif has_c:
        parts = x.split(",")
        if len(parts) > 2 or len(parts[-1]) == 3:
            x = x.replace(",", "")
        else:
            x = x.replace(",", ".")
    x = re.sub(r"[^0-9.]", "", x)
    if x.count(".") > 1:
        intp, _, frac = x.rpartition(".")
        x = intp.replace(".", "") + "." + frac
    try:
        v = float(x) if x not in ("", ".") else 0.0
    except ValueError:
        v = 0.0
    return -v if neg else v


def _clean_text(series: pd.Series) -> pd.Series:
    """Nettoie une colonne texte : strip puis title-case."""
    s = series.astype(str).str.strip()
    s = s.replace({"nan": "", "None": ""})
    s = s.str.title()
    return s


def _derive_region(country: pd.Series) -> pd.Series:
    """Déduit la région à partir du pays via ``COUNTRY_TO_REGION``."""
    # On normalise les clés du mapping pour une comparaison robuste.
    norm_map = {_canon_key(k): v for k, v in COUNTRY_TO_REGION.items()}

    def lookup(value: str) -> str:
        return norm_map.get(_canon_key(value), "Autre")

    return country.map(lookup)


def _derive_zone(country: pd.Series, zone_map: dict) -> pd.Series:
    """Zone de reporting : selon le mapping ``zone_map`` du client (ex. Kenzo :
    EU + CAN / USA / APAC). Si le pays n'y est pas, on retombe sur la **région**
    (Europe, Asie…) plutôt que « Autre »."""
    zmap = {_canon_key(k): v for k, v in (zone_map or {}).items()}
    rmap = {_canon_key(k): v for k, v in COUNTRY_TO_REGION.items()}

    def lookup(value: str) -> str:
        ck = _canon_key(value)
        return zmap.get(ck) or rmap.get(ck) or "Autre"

    return country.map(lookup)
