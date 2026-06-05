"""Création d'un brouillon Gmail (compte-rendu de performances SEA).

Les identifiants OAuth sont lus depuis les **Secrets Streamlit** (jamais dans le
dépôt, qui est public). Format attendu (.streamlit/secrets.toml) :

    [gmail]
    client_id     = "....apps.googleusercontent.com"
    client_secret = "...."
    refresh_token = "...."
    sender        = "moi@mondomaine.com"   # optionnel

Le module dégrade proprement : ``configured()`` renvoie False si la config
manque, et l'UI affiche alors les instructions d'activation. Le scope utilisé
est ``gmail.compose`` (création de brouillons uniquement — pas d'envoi).
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText

_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _secrets() -> dict:
    try:
        import streamlit as st
        if "gmail" in st.secrets:
            return dict(st.secrets["gmail"])
    except Exception:
        pass
    return {}


def configured() -> bool:
    """True si les 3 identifiants OAuth sont présents."""
    s = _secrets()
    return all(s.get(k) for k in ("client_id", "client_secret", "refresh_token"))


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    s = _secrets()
    creds = Credentials(
        None,
        refresh_token=s["refresh_token"],
        token_uri=_TOKEN_URI,
        client_id=s["client_id"],
        client_secret=s["client_secret"],
        scopes=_SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def create_draft(subject: str, body: str, to: str = "", html: str = "") -> str:
    """Crée un brouillon Gmail et renvoie son id. Lève si non configuré.

    Si ``html`` est fourni, le brouillon est mis en forme (tableaux, couleurs) ;
    sinon il est en texte brut."""
    if not configured():
        raise RuntimeError(
            "Gmail non configuré : ajoutez [gmail] dans les Secrets Streamlit.")
    s = _secrets()
    if html:
        msg = MIMEText(html, "html", "utf-8")
    else:
        msg = MIMEText(body or "", "plain", "utf-8")
    msg["Subject"] = subject or "Compte-rendu SEA"
    if to:
        msg["To"] = to
    if s.get("sender"):
        msg["From"] = s["sender"]
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = _service().users().drafts().create(
        userId="me", body={"message": {"raw": raw}}).execute()
    return draft.get("id", "")
