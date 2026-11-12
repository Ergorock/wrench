# Wrench

Wrench est une application de bureau Windows qui regroupe de petits outils du quotidien derrière une interface unique : un bandeau d'outils personnalisable (ordre, favoris), des paramètres (langue `fr`/`en`, thème clair, sombre ou système) et des notifications. Le socle (le shell) est livré avec un premier outil, « Raccourcis Windows » ; d'autres outils s'y branchent en suivant le guide [Créer un outil](docs/creating-a-tool.md).

## Prérequis

- Python 3.12 et [uv](https://docs.astral.sh/uv/)
- Node.js 22 ou plus récent
- Runtime WebView2 de Microsoft (présent par défaut sur Windows 11)

## Installation

```powershell
cd backend;  uv sync
cd ../frontend; npm ci
```

## Lancement en développement

```powershell
scripts/dev.ps1
```

Le script démarre Vite (`http://localhost:5173`), puis la fenêtre Wrench avec `WRENCH_DEV=1`, et arrête Vite à la fermeture. Les données de dev vont dans `%TEMP%\wrench-dev` sauf si `WRENCH_DATA_DIR` est défini. Les données réelles se trouvent dans `%APPDATA%\Wrench`.

## Tests et qualité

Dans `backend/` :

```powershell
uv run pytest
uv run ruff check .
uv run mypy src
```

Dans `frontend/` :

```powershell
npm test
npm run lint
npm run build
```

## Build

```powershell
scripts/build.ps1
```

Le script compile le front (`npm ci`, `npm run build`), synchronise le backend (`uv sync`), puis lance PyInstaller (`--onedir --windowed`). Il s'arrête à la première erreur. Résultat : `dist/Wrench/Wrench.exe`. Il faut distribuer le dossier `dist/Wrench/` en entier : l'exécutable seul ne suffit pas. Python n'est pas nécessaire sur le poste cible ; le runtime WebView2 l'est.

L'icône `backend/assets/wrench.ico` est provisoire. Elle se régénère avec `uv run --project backend python scripts/make_icon.py`.

## Installateur

Prérequis : [NSIS 3](https://nsis.sourceforge.io/) (`winget install NSIS.NSIS`). À défaut, le script utilise le `makensis` du cache d'electron-builder (`%LOCALAPPDATA%\electron-builder\Cache\nsis-*`) s'il existe.

```powershell
scripts/build-installer.ps1 [-SkipAppBuild]
```

Le script lance `scripts/build.ps1` (sauf avec `-SkipAppBuild`, qui réutilise `dist/Wrench/`), lit la version dans `backend/src/wrench/_version.py`, puis compile `installer/wrench.nsi` avec `makensis`. Résultat : `installer/Output/Wrench-Setup-<version>.exe`, qui s'installe pour l'utilisateur courant, sans droits administrateur.

Options de l'installateur : `/S` (installation silencieuse) et `/RELAUNCH` (relance Wrench à la fin, seulement avec `/S` ; utilisée par les mises à jour). En mode silencieux, si Wrench est encore ouvert après 30 s, l'installateur s'arrête avec le code 2 sans rien modifier. Désinstallation silencieuse : `"%LOCALAPPDATA%\Programs\Wrench\uninstall.exe" /S` (les paramètres et données de `%APPDATA%\Wrench` sont alors conservés).

L'installateur n'est pas signé : Windows SmartScreen affichera un avertissement au premier lancement (« Informations complémentaires », puis « Exécuter quand même »).

### Mises à jour

Wrench vérifie les nouvelles versions publiées sur GitHub (au démarrage puis toutes les 24 h, désactivable dans Paramètres > Général) et propose de les installer. Cela ne fonctionne que pour une version **installée** avec l'installateur : en développement ou depuis `dist/`, la section est grisée.

- Si une mise à jour échoue pendant l'installation, Wrench peut ne plus démarrer : relancez l'installateur, téléchargé dans `%TEMP%\Wrench-update\` ou disponible sur la page des releases.
- Les installateurs téléchargés restent dans `%TEMP%\Wrench-update\` : ils peuvent être supprimés sans risque.
- Certains antivirus ou protections d'entreprise bloquent les installateurs non signés.

## Documentation

- [Créer un outil](docs/creating-a-tool.md)
