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

Dans l’onglet **Routines**, créez des automatisations ou demandez-les dans le
chat, par exemple :

- `Au démarrage du PC, lance Valorant et Spotify`
- `Quand je lance osu, passe la résolution en natif`

Les routines sont enregistrées localement dans la base de données. Le
démarrage de CAPRI avec Windows se configure avec la case de l’onglet
**Routines** ; CAPRI démarre alors sans fenêtre ni console, reste accessible
dans la zone de notification et surveille les applications. Fermer la fenêtre
la réduit dans cette zone ; choisissez **Quitter CAPRI** dans son menu pour
arrêter le processus. Un fichier `.exe` n’est pas nécessaire : le raccourci de
démarrage lance l’interpréteur Python sans fenêtre de console.

La commande `Au démarrage du PC, lance ...` active aussi automatiquement le
démarrage de CAPRI avec Windows. Si cette configuration échoue, CAPRI indique
explicitement l’erreur et conserve la routine créée.

Les routines au démarrage de CAPRI lancent les applications via leurs
raccourcis vérifiés du menu Démarrer. Les routines déclenchées par une
application surveillent le processus correspondant au raccourci vérifié.
L’action de résolution applique à l’écran principal le mode ayant la plus
haute résolution annoncée par Windows. Vous pouvez activer, désactiver ou
supprimer une routine depuis l’onglet **Routines**. Les permissions de CAPRI
restent applicables aux actions automatisées.

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
