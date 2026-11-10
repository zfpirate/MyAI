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

## Application Windows et mises à jour

Téléchargez `CAPRI-windows-x64.zip` depuis les [releases GitHub](https://github.com/zfpirate/MyAI/releases),
extrayez le dossier `CAPRI` dans un emplacement où votre compte peut écrire,
par exemple `%LOCALAPPDATA%\Programs\CAPRI`, puis lancez `CAPRI.exe`. Dans
l'onglet **Mises à jour**, CAPRI vérifie les nouvelles releases GitHub et peut
télécharger, vérifier et installer une nouvelle version. Vos données sont
stockées séparément dans `%LOCALAPPDATA%\CAPRI\data` et ne sont pas remplacées
pendant une mise à jour.

Ollama doit toujours être installé et démarré avec le modèle `qwen3:8b`.
Pour compiler localement l'application Windows, lancez
`.\build_windows.ps1` depuis PowerShell ; ses dépendances de compilation sont
séparées dans `requirements-build.txt`. La publication d'un tag `v*` compile
l'application Windows et ajoute son archive ainsi que son empreinte SHA-256 à
la release GitHub.

### Ajouter les images de CAPRI

- Placez le logo horizontal au format PNG dans `assets/images/capri-logo.png`
  (fond transparent recommandé, environ 700 × 240 pixels).
- Placez l'icône carrée PNG dans `assets/icons/capri.png` (256 × 256 pixels
  conseillé) ; elle sera utilisée dans la fenêtre et la zone de notification.
- Pour l'icône du fichier EXE dans l'Explorateur Windows, ajoutez aussi
  `assets/icons/capri.ico` (multi-résolution, dont 256 × 256).

Relancez `.\build_windows.ps1` après avoir ajouté ou remplacé une image : les
fichiers du dossier `assets` sont intégrés au paquet et inclus dans les mises
à jour. Chaque push sur `main` crée automatiquement une release Windows avec
un numéro de version patch incrémenté. Les tags `v*` peuvent également être
compilés directement, et le workflow peut être lancé manuellement pour
reconstruire une release existante.

## Routines de démarrage

Dans l’onglet **Routines**, créez des automatisations ou demandez-les dans le
chat, par exemple :

- `Au démarrage du PC, lance Valorant et Spotify`
- `Quand je lance osu, passe la résolution en natif`
- `Mets la résolution en 1200 par 1080`

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

Lorsqu’une application vérifiée masque sa fenêtre au lieu de quitter
(comportement courant pour Discord), la commande `Ferme Discord` arrête aussi
les processus suivis de cette application après avoir revérifié leur chemin
et leur éditeur. CAPRI ne prétend pas que l’application est fermée si des
processus vérifiés restent actifs.

## Données locales

En mode développement, la mémoire est conservée dans `data/capri.db`. Dans
l'application Windows, elle est stockée dans
`%LOCALAPPDATA%\CAPRI\data\capri.db` afin que les mises à jour préservent les
données locales. Ces bases sont ignorées par Git.

## Dépôt GitHub

GitHub héberge ici le code source : CAPRI est une application de bureau Windows,
pas un site à déployer sur GitHub Pages. Avant de rendre le dépôt public,
vérifiez les fichiers ajoutés et choisissez une licence si vous souhaitez
autoriser la réutilisation du code.

## Dépendances

Les bibliothèques Python sont listées dans [`requirements.txt`](requirements.txt).
Ollama et le modèle `qwen3:8b` sont des prérequis distincts et ne sont pas
installés par pip.
