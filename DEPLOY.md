# 🚀 Mettre le dashboard en ligne (Streamlit Community Cloud)

Objectif : obtenir une URL publique du type `https://kenzo-sea.streamlit.app`
à envoyer à ta cliente. C'est **gratuit** et garde toutes les fonctions.

Il y a 3 étapes : (1) créer un compte GitHub, (2) y déposer le code,
(3) connecter Streamlit Cloud.

---

## 1. Créer un compte GitHub (5 min)

1. Va sur **https://github.com/signup**
2. Renseigne e-mail, mot de passe, nom d'utilisateur (ex. `cesar-sea`).
3. Valide l'e-mail de confirmation.

## 2. Déposer le code sur GitHub

### Option A — Tout en ligne (sans rien installer)
1. Sur GitHub, clique **+ (en haut à droite) → New repository**.
2. Nom : `sea-dashboard` · laisse **Private** (ou Public) · **Create repository**.
3. Sur la page du repo : **uploading an existing file**.
4. Glisse-dépose **tout le contenu** du dossier `sea-dashboard`
   **SAUF** le dossier `.venv` (volumineux et inutile).
   → Pense à inclure les dossiers `core/`, `views/`, `.streamlit/`,
   et les fichiers `app.py`, `requirements.txt`, `README.md`, `.gitignore`.
5. **Commit changes**.

### Option B — En ligne de commande (si tu préfères)
Je peux le faire avec toi : il suffit d'installer GitHub CLI puis
`gh auth login`. Dis-le-moi et je te donne les commandes exactes.

## 3. Déployer sur Streamlit Community Cloud

1. Va sur **https://share.streamlit.io** → **Sign in with GitHub**
   (autorise l'accès quand c'est demandé).
2. Clique **Create app → Deploy a public app from GitHub**.
3. Renseigne :
   - **Repository** : `ton-pseudo/sea-dashboard`
   - **Branch** : `main`
   - **Main file path** : `app.py`
4. (Optionnel) **Advanced settings → Python version : 3.11**.
5. Clique **Deploy**. Patiente ~2-3 min (installation des dépendances).

✅ Tu obtiens une URL `https://....streamlit.app` — partageable immédiatement.

---

## Mettre à jour le site plus tard
Modifie un fichier sur GitHub (ou re-upload) → Streamlit redéploie tout seul.

## Accès privé / mot de passe
Le tier gratuit de Streamlit Cloud peut **restreindre l'accès par e-mail**
(Settings → Sharing). Pour un **domaine perso + mot de passe simple**, on
passera sur **Render** (je te guiderai) — même code, ~30 min.

## Données
Aucune donnée n'est stockée : ta cliente importe son Excel à chaque session,
le dashboard lit les chiffres et affiche le rapport. Rien n'est conservé côté
serveur.
