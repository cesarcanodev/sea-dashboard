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

# Détection du type de campagne — liste ORDONNÉE de (motif, libellé).
# Le libellé est AFFICHÉ TEL QUEL (on respecte la nomenclature du client :
# « Brand Other », « Pure Brand », « Branded », « Brex », « DSA »…).
# Règles de correspondance (cf. normalizer.parse_campaign) :
#   • motif avec espace  → sous-chaîne dans le nom normalisé (ex. « pure brand »)
#   • motif d'un seul mot → token exact (évite « pla » trouvé dans « display »)
# L'ORDRE compte : le plus spécifique d'abord ; « brand » générique en dernier.
#
# Note métier : DSA et « Brand Other » sont la même famille ; « Pure Brand » et
# « Brex » aussi — mais on affiche le libellé réellement présent dans l'extract.
DEFAULT_TYPES = [
    # multi-mots (plus spécifiques) — testés en sous-chaîne
    ("performance max", "PMax"),
    ("pure brand", "Pure Brand"),
    ("brand other", "Brand Other"),
    ("search brand", "Search Brand"),
    ("demand gen", "Demand Gen"),
    ("non brand", "Gen"),
    # tokens (mot exact)
    ("pmax", "PMax"), ("pema", "PMax"), ("gpma", "PMax"),
    ("branded", "Branded"),
    ("brex", "Brex"),
    ("dsa", "DSA"),
    ("shopping", "PLA"), ("gsho", "PLA"), ("pla", "PLA"),
    ("display", "Display"),
    ("discovery", "Discovery"),
    ("youtube", "Video"), ("video", "Video"),
    ("generic", "Gen"), ("gen", "Gen"),
    # générique (fallback) — en dernier
    ("brand", "Search Brand"),
]

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
        "types": [],            # la liste par défaut suffit (Branded/Brex/PMax/PLA)
        "zones": _KENZO_ZONES,  # EU + CAN / USA / APAC
    },
    {
        "name": "IM EMAE",
        "match": ["im -", "pmax: im", "weekly im", "im emae"],
        "types": [],            # Pure Brand / PMax / DSA (liste par défaut)
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
    """Renvoie la config effective : {name, types (liste ordonnée), zones}.

    Les motifs propres au client (s'il y en a) sont placés AVANT les motifs par
    défaut → ils l'emportent.
    """
    client = detect_client(campaign_values)
    if client is None:
        return {"name": "Générique", "types": list(DEFAULT_TYPES),
                "zones": DEFAULT_ZONES}
    return {
        "name": client["name"],
        "types": list(client.get("types", [])) + list(DEFAULT_TYPES),
        "zones": client.get("zones", DEFAULT_ZONES),
    }
