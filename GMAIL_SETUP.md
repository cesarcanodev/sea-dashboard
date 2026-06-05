# 📧 Activer le brouillon Gmail (bouton dans l'app)

Le bouton **« Créer le brouillon dans Gmail »** (page *Rapport client*) pousse le
compte-rendu de performances dans tes **Brouillons** Gmail. Il faut le connecter
une seule fois. Le scope demandé est `gmail.compose` (**création de brouillons
uniquement — aucun envoi automatique, aucune lecture de mails**).

## 1. Créer des identifiants OAuth (Google Cloud, ~5 min)

1. Va sur **https://console.cloud.google.com/** → crée (ou choisis) un projet.
2. **APIs & Services → Library** → cherche **Gmail API** → **Enable**.
3. **APIs & Services → OAuth consent screen** → type **External** → renseigne
   le minimum (nom de l'app, ton e-mail) → ajoute-toi en **Test user**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** →
   type **Desktop app** → **Create** → **Download JSON**.
5. Renomme le fichier téléchargé en **`client_secret.json`** et place-le à la
   racine du projet (à côté du dossier `scripts/`).

## 2. Générer le refresh token (une fois, en local)

```bash
cd sea-dashboard
source .venv/bin/activate
pip install -r requirements.txt
python scripts/gmail_token.py
```

Une page Google s'ouvre → autorise. Le script affiche :

```
[gmail]
client_id     = "....apps.googleusercontent.com"
client_secret = "...."
refresh_token = "...."
sender        = "ton.email@gmail.com"
```

## 3. Coller dans les Secrets

- **En local** : crée `sea-dashboard/.streamlit/secrets.toml` et colle le bloc
  `[gmail]` ci-dessus. *(Ce fichier est ignoré par git — il ne partira pas sur
  GitHub.)*
- **En ligne (Streamlit Cloud)** : ton app → **⋮ → Settings → Secrets** → colle
  le même bloc `[gmail]` → **Save**. L'app redémarre.

## 4. Utiliser

Page **Rapport client** → section « Créer le brouillon Gmail » → (optionnel)
destinataire + objet → **Créer le brouillon**. Va dans Gmail → **Brouillons**.

---

⚠️ Ne mets **jamais** `client_secret.json` ni les identifiants dans le dépôt
GitHub (il est public). Tout passe par les Secrets Streamlit.
