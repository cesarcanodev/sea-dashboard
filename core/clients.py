"""Profils par client : reconnaissance automatique + règles de parsing.

Le logiciel détecte le client à partir des **noms de campagne** (sous-chaînes
``match``), puis applique ses ``types`` (en plus des types par défaut) et ses
``zones`` (regroupements géographiques). Si aucun client ne correspond, on
utilise la configuration par défaut (types = union de tous les tokens connus,
zone = région).

➕ POUR AJOUTER UN CLIENT : copie un bloc dans CLIENTS :
    {
        "name": "Nom du client",
        "match": ["sous-chaine1", "sous-chaine2"],   # repère dans les campagnes
        "types": {"TOKEN": "Type", ...},             # spécifique (facultatif)
        "zones": {"Pays": "Zone", ...},              # regroupements (facultatif)
    }
"""

from __future__ import annotations

# Types de campagne reconnus par défaut (union de tous les tokens connus).
DEFAULT_TYPES = {
    "PMAX": "PMax", "PEMA": "PMax", "GPMA": "PMax",
    "BREX": "Brex",
    "BRANDED": "Search Brand", "BRAND": "Search Brand", "BRAN": "Search Brand",
    "SBRAND": "Search Brand",
    "PLA": "PLA", "GSHO": "PLA", "SHOPPING": "PLA",
    "DSA": "DSA",
    "GEN": "Gen", "GENERIC": "Gen", "NONBRAND": "Gen",
}

# Zone par défaut : vide → on retombe sur la région (Europe, Amérique…).
DEFAULT_ZONES: dict = {}

# Zones « EU + CAN / USA / APAC » — taxonomie Kenzo.
_KENZO_ZONES = {
    "France": "EU + CAN", "Allemagne": "EU + CAN", "Espagne": "EU + CAN",
    "Italie": "EU + CAN", "Royaume-Uni": "EU + CAN", "Belgique": "EU + CAN",
    "Pays-Bas": "EU + CAN", "Suisse": "EU + CAN", "Portugal": "EU + CAN",
    "Irlande": "EU + CAN", "Canada": "EU + CAN", "Multi-pays": "EU + CAN",
    "Europe": "EU + CAN",
    "États-Unis": "USA",
    "Hong Kong": "APAC", "Malaisie": "APAC", "Singapour": "APAC",
    "Australie": "APAC", "Pan-Asie": "APAC", "Japon": "APAC", "Chine": "APAC",
    "Inde": "APAC", "Corée Du Sud": "APAC", "Indonésie": "APAC",
}

CLIENTS = [
    {
        "name": "Kenzo",
        "match": ["kenzocouture", "kenzo"],
        "types": {},            # l'union par défaut suffit (PLA/PMax/Brex/Brand)
        "zones": _KENZO_ZONES,  # EU + CAN / USA / APAC
    },
    {
        "name": "IM EMAE",
        "match": ["im -", "pmax: im", "weekly im", "im emae"],
        "types": {},            # Search Brand / PMax / DSA (union par défaut)
        "zones": {},            # vide → région (Europe)
    },
]


def detect_client(campaign_values) -> dict | None:
    """Reconnaît le client en comptant les correspondances dans les campagnes."""
    vals = [str(v).lower() for v in campaign_values if str(v).strip()]
    best, best_score = None, 0
    for client in CLIENTS:
        subs = [s.lower() for s in client.get("match", [])]
        score = sum(1 for v in vals if any(s in v for s in subs))
        if score > best_score:
            best, best_score = client, score
    return best


def config_for(campaign_values) -> dict:
    """Renvoie la config effective : {name, types (fusionnés), zones}."""
    client = detect_client(campaign_values)
    if client is None:
        return {"name": "Générique", "types": dict(DEFAULT_TYPES),
                "zones": DEFAULT_ZONES}
    return {
        "name": client["name"],
        "types": {**DEFAULT_TYPES, **client.get("types", {})},
        "zones": client.get("zones", DEFAULT_ZONES),
    }
