"""Génère un refresh_token Google Ads (à exécuter UNE fois, en local).

Prérequis :
  1. Un **developer token** Google Ads (API Center d'un compte MCC — voir
     GOOGLE_ADS_SETUP.md). Indispensable pour appeler l'API ensuite.
  2. Des identifiants OAuth « Application de bureau » (Google Cloud Console) →
     télécharger le JSON et le renommer ``client_secret.json`` (à côté de ce
     script).
  3. pip install google-auth-oauthlib

Lancement :
    python scripts/google_ads_token.py

Une fenêtre de consentement Google s'ouvre. Après autorisation, le script
affiche le bloc [google_ads] à recopier dans les Secrets Streamlit.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n=== À copier dans les Secrets Streamlit ===\n")
    print("[google_ads]")
    print('developer_token   = "TON_DEVELOPER_TOKEN"   # depuis l\'API Center MCC')
    print(f'client_id         = "{creds.client_id}"')
    print(f'client_secret     = "{creds.client_secret}"')
    print(f'refresh_token     = "{creds.refresh_token}"')
    print('login_customer_id = "1234567890"   # optionnel : ID du compte MCC')


if __name__ == "__main__":
    main()
