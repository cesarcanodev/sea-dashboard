"""Classement IA des campagnes inconnues (repli quand les règles échouent).

Quand les règles de ``normalizer`` ne reconnaissent pas le type d'une campagne,
on demande à Claude de déduire {type, pays} en choisissant dans une **liste
fermée** de types. Conçu pour :
  • dégrader proprement sans clé API (renvoie {} → on garde les règles) ;
  • ne rappeler l'API que pour des noms **nouveaux** (cache en mémoire) ;
  • borner le coût (sortie structurée, prompt caching du système).

La clé est lue depuis les Secrets Streamlit (``ANTHROPIC_API_KEY``) ou la
variable d'environnement du même nom — jamais en dur dans le code.
"""

from __future__ import annotations

import os
from typing import List, Optional

# Modèle par défaut (cf. guide d'intégration de l'API Claude).
_MODEL = "claude-opus-4-8"

# Types autorisés (liste fermée) — alignés sur nos libellés.
ALLOWED_TYPES = [
    "PLA", "PMax", "Search Brand", "DSA", "Brex", "Gen",
    "Display", "Demand Gen", "Video", "Discovery", "App", "Autre",
]

_SYSTEM = (
    "Tu classes des noms de campagnes Google Ads (SEA). Pour chaque nom, "
    "déduis deux champs :\n"
    "1) type : EXACTEMENT l'une de ces valeurs — "
    "PLA, PMax, Search Brand, DSA, Brex, Gen, Display, Demand Gen, Video, "
    "Discovery, App, Autre.\n"
    "   Indices : 'pmax'/'performance max'→PMax ; 'pla'/'shopping'/'gsho'→PLA ; "
    "'brand'/'branded'/'sbrand'→Search Brand ; 'brex'→Brex ; "
    "'dsa'/'dynamic search'→DSA ; 'gen'/'generic'/'non brand'/'nonbrand'→Gen ; "
    "'display'→Display ; 'demand gen'/'demandgen'/'dgen'→Demand Gen ; "
    "'video'/'youtube'/'yt'→Video ; 'discovery'→Discovery ; 'app'→App ; "
    "si vraiment indéterminable→Autre.\n"
    "2) country : le PAYS en français (ex. 'France', 'Allemagne', "
    "'États-Unis', 'Slovaquie') déduit d'un code présent dans le nom "
    "(FR, DE, USA, SK/EN, IT/IT…) ; null si aucun pays n'est identifiable.\n"
    "Ne te fie qu'au nom fourni. Réponds via le format structuré demandé."
)

# Cache en mémoire par nom de campagne (persiste sur la durée du serveur).
_CACHE: dict[str, dict] = {}
_CHUNK = 80  # nb de campagnes par appel API


def _get_key() -> str | None:
    try:
        import streamlit as st
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def available() -> bool:
    """True si une clé API est configurée (l'IA peut être appelée)."""
    return bool(_get_key())


def classify(names) -> dict:
    """Renvoie {nom: {"type": str, "country": str|None}} pour les noms fournis.

    Sans clé API → {}. Les noms déjà vus sont servis depuis le cache.
    """
    key = _get_key()
    uniq = [n for n in dict.fromkeys(str(x) for x in names) if n.strip()]
    if not key or not uniq:
        return {}
    todo = [n for n in uniq if n not in _CACHE]
    for i in range(0, len(todo), _CHUNK):
        chunk = todo[i:i + _CHUNK]
        try:
            _CACHE.update(_call_api(key, chunk))
        except Exception:
            # Échec réseau / quota / import : on ne bloque jamais le dashboard.
            break
    return {n: _CACHE[n] for n in uniq if n in _CACHE}


def _call_api(key: str, names: list) -> dict:
    """Un appel Claude (sortie structurée) pour un lot de noms."""
    import anthropic
    from pydantic import BaseModel

    class _Item(BaseModel):
        name: str
        type: str
        country: Optional[str]

    class _Result(BaseModel):
        items: List[_Item]

    client = anthropic.Anthropic(api_key=key)
    user = "Classe ces campagnes :\n" + "\n".join(f"- {n}" for n in names)
    resp = client.messages.parse(
        model=_MODEL,
        max_tokens=8000,
        system=[{"type": "text", "text": _SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=_Result,
    )
    out: dict = {}
    parsed = resp.parsed_output
    if parsed:
        allowed = set(ALLOWED_TYPES)
        for it in parsed.items:
            t = it.type if it.type in allowed else "Autre"
            out[it.name] = {"type": t, "country": it.country or None}
    return out
