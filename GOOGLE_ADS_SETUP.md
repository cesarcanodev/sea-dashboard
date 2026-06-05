# 🔗 Connecter Google Ads à l'application

Le bouton **« Importer depuis Google Ads »** (sidebar) récupère les performances
journalières par campagne directement via l'**API Google Ads**, et les fait
passer par le **même traitement** que tes fichiers Excel (types, familles, zones,
détection du client). Plus besoin d'exporter à la main.

Connexion en lecture seule : le scope demandé est `adwords` et l'app ne fait que
des requêtes `SELECT` (aucune modification de tes campagnes).

---

## 1. Obtenir un *developer token* (le prérequis qui demande une validation)

C'est l'élément qui débloque l'API — il se demande **une fois**, sur un compte
**MCC (centre multi-comptes)** :

1. Connecte-toi au **MCC** → **Outils & paramètres → Configuration → API Center**.
2. Note le **developer token** affiché.
3. Son **niveau d'accès** : par défaut « Test » (ne lit que des comptes de test).
   Pour lire tes vrais comptes, demande l'**accès Basic** depuis cette page
   (formulaire Google) → validation sous quelques jours en général.

> Sans developer token avec accès Basic, l'API renverra une erreur
> d'autorisation. Tout le reste de l'app est prêt et fonctionnera dès qu'il est
> actif.

## 2. Identifiants OAuth (Google Cloud, ~5 min)

1. **https://console.cloud.google.com/** → projet (le même que Gmail convient).
2. **APIs & Services → Library** → active **Google Ads API**.
3. **OAuth consent screen** → External → ajoute-toi en **Test user**.
4. **Credentials → Create credentials → OAuth client ID** → **Desktop app** →
   **Download JSON** → renomme en **`client_secret.json`** à la racine du projet.

## 3. Générer le refresh token (une fois, en local)

```bash
cd sea-dashboard
source .venv/bin/activate
pip install -r requirements.txt
python scripts/google_ads_token.py
```

Autorise dans la fenêtre Google. Le script affiche un bloc `[google_ads]`.

## 4. Coller dans les Secrets

Complète le bloc avec ton **developer_token** (étape 1) et, si tu passes par un
MCC, le **login_customer_id** (l'ID du MCC, 10 chiffres) :

```toml
[google_ads]
developer_token   = "xxxxxxxxxxxxxxxxxxxxxx"
client_id         = "....apps.googleusercontent.com"
client_secret     = "...."
refresh_token     = "...."
login_customer_id = "1234567890"   # optionnel (compte MCC / agence)
```

- **En local** : dans `sea-dashboard/.streamlit/secrets.toml`.
- **En ligne (Streamlit Cloud)** : app → **⋮ → Settings → Secrets** → colle →
  **Save** (l'app redémarre).

## 5. Utiliser

Sidebar → **🔗 Google Ads** → saisis l'**ID client** (10 chiffres, ex.
`123-456-7890`) du compte à analyser → choisis la période → **Importer depuis
Google Ads**. (Le dépliant « Trouver mon ID client » liste les comptes
accessibles.)

---

⚠️ Ne mets **jamais** `client_secret.json`, le developer token ou le refresh
token dans le dépôt GitHub (il est public). Tout passe par les Secrets Streamlit.
`google-ads.yaml` et `client_secret.json` sont ignorés par git.
