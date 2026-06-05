"""Génère un refresh_token Gmail (à exécuter UNE fois, en local).

Prérequis :
  1. Google Cloud Console → activer l'API Gmail.
  2. Créer des identifiants OAuth « Application de bureau » → télécharger le
     fichier JSON et le renommer ``client_secret.json`` (à côté de ce script).
  3. pip install google-auth-oauthlib

Lancement :
    python scripts/gmail_token.py

Une fenêtre de consentement Google s'ouvre. Après autorisation, le script
affiche client_id / client_secret / refresh_token à recopier dans les Secrets
Streamlit, section [gmail].
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n=== À copier dans les Secrets Streamlit ===\n")
    print("[gmail]")
    print(f'client_id     = "{creds.client_id}"')
    print(f'client_secret = "{creds.client_secret}"')
    print(f'refresh_token = "{creds.refresh_token}"')
    print('sender        = "ton.email@gmail.com"   # optionnel')


if __name__ == "__main__":
    main()
