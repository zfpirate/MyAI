# CAPRI

CAPRI est une application de bureau personnelle en Python. Elle propose une
interface de chat, une mémoire locale, un suivi du système et des actions
Windows avec confirmation pour certaines opérations.

## Prérequis

- Windows 10 ou 11
- Python 3.10 ou plus récent
- [Ollama](https://ollama.com/) installé et démarré localement
- Le modèle `qwen3:8b` disponible dans Ollama

Téléchargez le modèle avec :

```powershell
ollama pull qwen3:8b
```

## Installation

Depuis le dossier du projet, créez un environnement virtuel et installez les
dépendances :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Lancez ensuite l’application :

```powershell
python main.py
```

## Routines de démarrage

Dans l’onglet **Routines**, saisissez les applications à ouvrir, par exemple
`Spotify et Riot Client`, puis créez la routine. Vous pouvez aussi demander dans
le chat : `Quand CAPRI démarre, ouvre Spotify et Riot Client`.

Les routines sont enregistrées localement dans la base de données et lancées
au prochain démarrage de CAPRI. Vous pouvez les activer, les désactiver ou les
supprimer depuis l’onglet **Routines**. Une routine ne contourne pas les
permissions : toute action nécessitant une confirmation n’est pas approuvée
automatiquement.

## Données locales

La mémoire de l’application est conservée dans `data/capri.db`. Cette base est
ignorée par Git afin de ne pas publier de données personnelles. Elle est créée
automatiquement au premier lancement sur une nouvelle installation.

## Dépôt GitHub

GitHub héberge ici le code source : CAPRI est une application de bureau Windows,
pas un site à déployer sur GitHub Pages. Avant de rendre le dépôt public,
vérifiez les fichiers ajoutés et choisissez une licence si vous souhaitez
autoriser la réutilisation du code.

## Dépendances

Les bibliothèques Python sont listées dans [`requirements.txt`](requirements.txt).
Ollama et le modèle `qwen3:8b` sont des prérequis distincts et ne sont pas
installés par pip.
