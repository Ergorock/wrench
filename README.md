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

## Documentation

- [Spécification du shell](docs/superpowers/specs/2026-11-12-wrench-shell-design.md)
- [Créer un outil](docs/creating-a-tool.md)
- [Feuille de route](docs/ROADMAP.md)
