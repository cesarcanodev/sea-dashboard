"""Connexion Google Ads → DataFrame brut (puis normalize() comme les fichiers).

Les identifiants sont lus depuis les **Secrets Streamlit** (jamais dans le dépôt,
qui est public). Format attendu (.streamlit/secrets.toml) :

    [google_ads]
    developer_token   = "xxxxxxxxxxxxxxxxxxxxxx"
    client_id         = "....apps.googleusercontent.com"
    client_secret     = "...."
    refresh_token     = "...."
    login_customer_id = "1234567890"   # optionnel : compte MCC / agence

Scope OAuth : ``https://www.googleapis.com/auth/adwords``.

Le module dégrade proprement : ``configured()`` renvoie False si la config
manque, et l'UI affiche alors les instructions d'activation (GOOGLE_ADS_SETUP.md).
Les données récupérées repassent par ``normalizer.normalize`` — donc types,
familles, zones et détection du client fonctionnent comme pour un import Excel.
"""

from __future__ import annotations

import pandas as pd

_REQUIRED = ("developer_token", "client_id", "client_secret", "refresh_token")

# Perfs journalières par campagne. On récupère le nom de campagne (le pays et le
# type en sont déduits côté normalizer, comme pour les fichiers) et les mesures
# brutes. Le coût est en micros (÷ 1 000 000) ; la valeur de conversion = CA.
_GAQL = """
    SELECT
      segments.date,
      campaign.name,
      campaign.bidding_strategy_type,
      campaign.maximize_conversion_value.target_roas,
      campaign.maximize_conversions.target_cpa_micros,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions,
      metrics.conversions_value
    FROM campaign
    WHERE segments.date BETWEEN '{start}' AND '{end}'
      AND metrics.impressions > 0
"""


def _bidding_name(campaign) -> str:
    """Nom lisible de la stratégie d'enchères (enum → texte)."""
    try:
        return campaign.bidding_strategy_type.name.replace("_", " ").title()
    except Exception:
        return ""


def _secrets() -> dict:
    try:
        import streamlit as st
        if "google_ads" in st.secrets:
            return dict(st.secrets["google_ads"])
    except Exception:
        pass
    return {}


def configured() -> bool:
    """True si les identifiants OAuth + developer token sont présents."""
    s = _secrets()
    return all(s.get(k) for k in _REQUIRED)


def _client():
    from google.ads.googleads.client import GoogleAdsClient

    s = _secrets()
    cfg = {
        "developer_token": s["developer_token"],
        "client_id": s["client_id"],
        "client_secret": s["client_secret"],
        "refresh_token": s["refresh_token"],
        "use_proto_plus": True,
    }
    if s.get("login_customer_id"):
        cfg["login_customer_id"] = _digits(s["login_customer_id"])
    return GoogleAdsClient.load_from_dict(cfg)


def _digits(customer_id) -> str:
    """Garde uniquement les chiffres d'un ID client (« 123-456-7890 » → …)."""
    return "".join(ch for ch in str(customer_id) if ch.isdigit())


def accessible_customers() -> list[str]:
    """Liste les ID des comptes accessibles avec ces identifiants (aide à
    retrouver le bon ID client). Renvoie [] en cas d'échec."""
    try:
        client = _client()
        svc = client.get_service("CustomerService")
        res = svc.list_accessible_customers()
        return [rn.split("/")[-1] for rn in res.resource_names]
    except Exception:
        return []


def fetch_raw(customer_id: str, start: str, end: str) -> pd.DataFrame:
    """Récupère les perfs journalières par campagne sur [start, end] (format
    ISO « YYYY-MM-DD ») et renvoie un DataFrame « brut » aux colonnes lisibles,
    prêt à passer dans ``normalizer.normalize`` (même chemin que les fichiers).
    """
    if not configured():
        raise RuntimeError(
            "Google Ads non configuré : ajoute le bloc [google_ads] dans les "
            "Secrets Streamlit (voir GOOGLE_ADS_SETUP.md).")
    cid = _digits(customer_id)
    if len(cid) != 10:
        raise ValueError("ID client invalide : il doit comporter 10 chiffres "
                         "(ex. 123-456-7890).")

    client = _client()
    service = client.get_service("GoogleAdsService")
    query = _GAQL.format(start=start, end=end)

    rows = []
    for batch in service.search_stream(customer_id=cid, query=query):
        for r in batch.results:
            c = r.campaign
            tcpa_micros = getattr(c.maximize_conversions, "target_cpa_micros", 0) or 0
            troas = getattr(c.maximize_conversion_value, "target_roas", 0) or 0
            rows.append({
                "Date": r.segments.date,
                "Campaign": c.name,
                "Bidding strategy": _bidding_name(c),
                "Target ROAS": float(troas),
                "Target CPA": tcpa_micros / 1_000_000,
                "Clicks": r.metrics.clicks,
                "Cost": r.metrics.cost_micros / 1_000_000,
                "Conversions": r.metrics.conversions,
                "Conv value": r.metrics.conversions_value,
            })
    return pd.DataFrame(rows)
