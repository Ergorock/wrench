# Créer un outil Wrench

Ce guide explique comment ajouter un outil à Wrench **sans modifier la coquille**. L'outil « Raccourcis Windows » (`windows_shortcuts`) sert d'exemple : les extraits de code ci-dessous viennent de ses fichiers réels.

Un outil est intégré à l'application : il vit dans le dépôt, dans deux dossiers jumeaux, et l'utilisateur peut l'activer ou le désactiver dans les paramètres.

## 1. Vue d'ensemble

### Les deux dossiers jumeaux

Un outil de même `id` occupe deux dossiers :

```
backend/src/wrench/tools/<id>/        # Python
├─ __init__.py                        # vide
├─ manifest.py                        # exporte MANIFEST
├─ service.py                         # exporte SERVICE
└─ data/…                             # facultatif : données embarquées

frontend/src/tools/<id>/              # Vue + TypeScript
├─ index.ts                           # export par défaut : chargeur du composant
├─ <Composant>.vue
├─ i18n/fr.json
└─ i18n/en.json
```

Pour `windows_shortcuts`, le composant est `ShortcutsTool.vue` et le backend a un dossier `data/` avec `shortcuts.json`.

### Cycle de vie

1. **Découverte (backend).** Au démarrage, `discover_tools()` parcourt le package `wrench.tools`. Pour chaque sous-paquet, elle lit `MANIFEST` dans `manifest.py` et `SERVICE` dans `service.py`. Un outil invalide (manifeste incorrect, `id` différent du nom du dossier, catégorie inconnue, `SERVICE` qui n'est pas une sous-classe de `ToolService`) est **écarté et journalisé** : l'application démarre quand même.
2. **Découverte (frontend).** `shell/toolComponents.ts` indexe les `frontend/src/tools/*/index.ts` avec `import.meta.glob`. `i18n/index.ts` charge les `frontend/src/tools/*/i18n/*.json` et les monte sous la clé `tools.<id>`.
3. **Activation.** L'outil est actif si `settings.tools[<id>].enabled` vaut `true` ou, à défaut, si `enabled_by_default` vaut `true` dans le manifeste. L'utilisateur le change dans *Paramètres > Outils*. C'est le frontend qui masque un outil inactif (bandeau, favoris). Désactiver un outil conserve ses données.
4. **Appel d'une action.** Le composant appelle `useTool("<id>").call("<action>", payload)`. L'appel passe par le pont (`window.pywebview.api.tool_call`), puis `Api.tool_call`, puis `ToolRegistry.call`, qui crée le service au premier appel et sérialise les actions d'un même outil. La réponse revient dans l'enveloppe `{ok: true, data}` ou `{ok: false, error: {code, message}}` ; le client du pont transforme l'erreur en `BridgeError`.

> En développement, relancez `scripts/dev.ps1` après avoir ajouté un outil : le backend ne découvre les outils qu'au démarrage.

## 2. Choisir l'id et la catégorie

- **Id** : snake_case, expression régulière `^[a-z][a-z0-9_]*$`, unique, **identique au nom des deux dossiers** (`windows_shortcuts`).
- **Version** : `^\d+\.\d+\.\d+$` (par exemple `1.0.0`).
- **Catégorie** : l'id d'une catégorie existante de `backend/src/wrench/core/categories.py`. Catégories actuelles, dans l'ordre : `system` (icône `monitor`), `productivity` (`zap`), `development` (`code`), `files` (`folder`).
- Les catégories sans outil actif sont masquées dans le bandeau.

### Ajouter une catégorie

1. Ajouter une ligne dans `CATEGORIES` de `backend/src/wrench/core/categories.py` : `Category("mon_id", "nom-icone-lucide")`. L'ordre du tuple est l'ordre d'affichage par défaut.
2. Ajouter le libellé `categories.mon_id` dans `frontend/src/i18n/fr.json` **et** `frontend/src/i18n/en.json`.
3. Ajouter l'icône dans `frontend/src/shell/iconTable.ts` (voir la section 4).

## 3. Backend

### `manifest.py`

```python
from wrench.sdk import ToolManifest

MANIFEST = ToolManifest(
    id="windows_shortcuts",
    category="system",
    icon="keyboard",
    version="1.0.0",
    enabled_by_default=True,
)
```

`icon` est un nom d'icône Lucide en kebab-case. Il doit figurer dans la table `frontend/src/shell/iconTable.ts` (section 4) : un test de contrat le vérifie.

### `service.py`

Le service est une classe qui hérite de `ToolService`. Ses actions sont des méthodes décorées par `@action`. Le module exporte la classe sous le nom `SERVICE`.

```python
from pydantic import BaseModel

from wrench.sdk import ToolError, ToolService, action

# Les modèles Pydantic (Shortcut, ShortcutGroup, Catalog) sont définis dans le même fichier.

class WindowsShortcutsService(ToolService):
    @action
    def get_catalog(self) -> Catalog:
        return Catalog(groups=list(_load_groups()), favorites=self._favorites())

    @action
    def set_favorite(self, shortcut_id: str, favorite: bool) -> list[str]:
        if shortcut_id not in _known_ids():
            raise ToolError("unknown_shortcut", f"Unknown shortcut: {shortcut_id}")
        favorites = self._favorites()
        if favorite and shortcut_id not in favorites:
            favorites.append(shortcut_id)
        elif not favorite and shortcut_id in favorites:
            favorites.remove(shortcut_id)
        data = self.ctx.storage.load()
        data["favorites"] = favorites
        self.ctx.storage.save(data)
        return favorites

SERVICE = WindowsShortcutsService
```

Règles à connaître :

- **Entrées.** Le `payload` envoyé par le frontend est un objet JSON dont les clés correspondent aux paramètres de l'action (`{"shortcut_id": "snap_left", "favorite": true}`). Pydantic valide les arguments ; un payload incorrect renvoie l'erreur `invalid_payload`.
- **Sorties.** Le résultat est validé d'après l'annotation de retour, puis sérialisé en JSON. Utilisez des modèles Pydantic (`BaseModel`) pour les structures :

  ```python
  class Shortcut(BaseModel):
      id: str
      keys: list[str]
  ```
- **Visibilité.** Seules les méthodes décorées par `@action` sont appelables. Un nom qui commence par `_` ne l'est jamais. Une action inconnue renvoie `unknown_action`.
- **Erreurs métier.** Levez `ToolError(code, message)`. Le `code` (snake_case) est ce que le frontend traduit (section 5). Toute autre exception devient l'erreur `internal_error`, journalisée.

### Le contexte `self.ctx`

Le constructeur du service reçoit un `ToolContext` :

| Attribut | Rôle |
|---|---|
| `ctx.storage` | `load() -> dict` et `save(dict)`. Fichier `%APPDATA%\Wrench\tools\<id>.json`, écriture atomique. Un fichier absent ou corrompu donne `{}`. |
| `ctx.language` | `"fr"` ou `"en"`, la langue courante de l'interface. |
| `ctx.logger` | Un `logging.Logger` nommé `wrench.tools.<id>`. |
| `ctx.tool_id` | L'id de l'outil. |

Ne lisez jamais un fichier de l'utilisateur en dehors de `ctx.storage` pour les données de l'outil. Tenez compte de données périmées : `windows_shortcuts` ignore dans `get_catalog` un favori dont l'id n'existe plus.

### Embarquer des données

Placez-les dans `backend/src/wrench/tools/<id>/data/` et lisez-les avec `importlib.resources`, une seule fois :

```python
@functools.cache
def _load_groups() -> tuple[ShortcutGroup, ...]:
    path = resources.files("wrench.tools.windows_shortcuts") / "data" / "shortcuts.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(ShortcutGroup.model_validate(g) for g in raw["groups"])
```

## 4. Frontend

### `index.ts`

L'export par défaut est un chargeur : le composant n'est téléchargé que quand l'outil est ouvert.

```ts
export default () => import('./ShortcutsTool.vue')
```

Si le chargement échoue, la coquille affiche un message traduit avec un bouton « Réessayer », puis l'accueil. L'erreur est écrite dans la console du WebView (visible en mode dev), pas dans `wrench.log`.

### Le composant

C'est un composant Vue en `<script setup lang="ts">`. La coquille affiche déjà l'en-tête de la page (icône du manifeste et titre `tools.<id>.name`) : le composant ne dessine que le contenu. Il appelle le backend avec `useTool` et ses textes avec `useI18n` :

```ts
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import type { Catalog } from './types'

const { t } = useI18n()
const tool = useTool('windows_shortcuts')
const catalog = ref<Catalog | null>(null)

const data = await tool.call<Catalog>('get_catalog')
const favorites = await tool.call<string[]>('set_favorite', { shortcut_id: id, favorite: true })
```

Dans `ShortcutsTool.vue`, ces appels sont faits dans des fonctions `async` (`load()` au montage, `toggleFavorite()` au clic). Les types TypeScript du frontend (`types.ts`) doivent refléter exactement les modèles Pydantic du backend.

**Gestion des erreurs : ne pas afficher de toast soi-même.** `useTool` affiche déjà le toast d'erreur (traduit) quand une action échoue, puis relance l'exception. Votre composant attrape l'exception pour rétablir son état (par exemple annuler une mise à jour optimiste), mais **ne doit pas afficher un deuxième toast** :

```ts
try {
  confirmed.value = await tool.call<string[]>('set_favorite', { shortcut_id: id, favorite: wanted })
} catch {
  // useTool a déjà affiché le toast ; l'opération en attente est retirée dans le finally
} finally {
  pendingToggles.value = pendingToggles.value.filter((p) => p.token !== op.token)
}
```

Pour une mise à jour optimiste, ne mémorisez pas « l'état précédent » pour y revenir en cas d'échec : deux clics rapprochés se marcheraient dessus. `ShortcutsTool.vue` garde plutôt l'état confirmé par le backend (`confirmed`) et la liste des opérations en attente (`pendingToggles`) ; l'état affiché (`favorites`) est calculé en appliquant les opérations en attente à l'état confirmé, et les appels sont envoyés l'un après l'autre.

`pushToast(message, 'info')` reste utile pour un message d'information qui ne vient pas d'une erreur d'action.

### Textes : tout passe par l'i18n

Aucun texte en dur dans un composant. Les clés de l'outil sont montées sous `tools.<id>.` :

```ts
const PREFIX = 'tools.windows_shortcuts.'
t(`${PREFIX}searchPlaceholder`)
```

### Couleurs et style

Utilisez uniquement les variables CSS du thème (`frontend/src/theme/theme.css`) : `--bg`, `--bg-elevated`, `--text`, `--text-muted`, `--border`, `--accent`, `--accent-text`, `--hover`, `--active`, `--warning-bg`, `--warning-border`, `--danger`, `--radius`, `--font`. Aucune couleur en dur : le rendu doit être correct en thème clair et en thème sombre.

### Icônes

Lucide uniquement, depuis `@lucide/vue`.

- **Dans un composant**, importez l'icône par son nom : `import { Star } from '@lucide/vue'`.
- **Dans un manifeste ou une catégorie**, l'icône est désignée par son nom kebab-case (`keyboard`). La coquille la retrouve dans la table explicite `frontend/src/shell/iconTable.ts`, qui replie sur `Box` pour un nom inconnu. Si votre icône n'y est pas, ajoutez-la : import nommé de `@lucide/vue` et une ligne dans la table. Le test de contrat Python échoue tant que l'icône d'un manifeste ou d'une catégorie manque.

## 5. Traductions

`frontend/src/tools/<id>/i18n/fr.json` et `en.json` ont **exactement les mêmes clés**. Clés obligatoires : `name` et `description`. Structure de `windows_shortcuts` :

```json
{
  "name": "Raccourcis Windows",
  "description": "Les raccourcis clavier de Windows 11, groupés et faciles à rechercher.",
  "searchPlaceholder": "Rechercher un raccourci…",
  "errors": { "unknown_shortcut": "Ce raccourci n’existe pas." },
  "groups": { "general": "Général" },
  "keys": { "Shift": "Maj" },
  "shortcuts": { "snap_left": "Ancrer la fenêtre à gauche de l’écran" }
}
```

### Erreurs propres à l'outil

Quand une action lève `ToolError("unknown_shortcut", …)`, le message affiché est cherché dans cet ordre :

1. `tools.<id>.errors.<code>` (l'outil) ;
2. `errors.<code>` (la coquille) ;
3. `errors.generic`.

Pour traduire une erreur de votre outil, ajoutez donc `errors.<code>` dans vos deux fichiers de langue.

## 6. Tests

### Service (pytest)

Testez le service sans l'application : un `ToolContext` sur un dossier temporaire suffit. Voir `backend/tests/test_windows_shortcuts.py`.

```python
@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "windows_shortcuts",
        ToolStorage(tmp_path / "windows_shortcuts.json"),
        lambda: "en",
        logging.getLogger("test"),
    )

@pytest.fixture
def svc(ctx: ToolContext) -> WindowsShortcutsService:
    return WindowsShortcutsService(ctx)

def test_unknown_shortcut(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("set_favorite", {"shortcut_id": "nope", "favorite": True})
    assert e.value.code == "unknown_shortcut"
```

`svc.invoke("<action>", {…})` passe par la même validation que l'application.

### Logique du frontend (vitest)

Isolez la logique pure (recherche, tri…) dans un fichier TypeScript testable, comme `search.ts` et `frontend/tests/windows_shortcuts.search.test.ts`. Un composant se teste en le montant avec `createApp` et un faux `window.pywebview.api` (voir `frontend/tests/windows_shortcuts.component.test.ts`).

### Test de contrat (automatique)

`backend/tests/test_tool_contract.py` s'exécute pour chaque outil découvert. Il vérifie que :

- le manifeste est valide et la catégorie existe ;
- `frontend/src/tools/<id>/index.ts` existe ;
- `fr.json` et `en.json` ont les mêmes clés, dont `name` et `description` ;
- l'icône du manifeste figure dans `iconTable.ts`.

Il détecte aussi un dossier d'outil écarté par le registre.

## 7. Checklist finale

- [ ] L'id respecte `^[a-z][a-z0-9_]*$` et les deux dossiers jumeaux portent exactement ce nom.
- [ ] `MANIFEST` est valide : catégorie existante, version `x.y.z`, icône présente dans `iconTable.ts`.
- [ ] `service.py` exporte `SERVICE` ; chaque action a des entrées et une sortie typées.
- [ ] `index.ts` exporte le chargeur du composant.
- [ ] `fr.json` et `en.json` ont les mêmes clés (dont `name` et `description`) et traduisent les `ToolError` de l'outil sous `errors.<code>`.
- [ ] Aucun texte ni aucune couleur en dur dans le composant ; aucun `pushToast` pour une erreur d'action.
- [ ] `cd backend; uv run pytest; uv run ruff check .; uv run mypy src`
- [ ] `cd frontend; npm test; npm run lint; npm run build`
- [ ] Vérification manuelle avec `scripts/dev.ps1` : rendu en thème clair et sombre, en français et en anglais ; l'outil s'ouvre, se désactive puis se réactive dans *Paramètres > Outils*, et ses données persistent.
