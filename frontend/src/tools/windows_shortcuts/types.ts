// Mirrors of the Pydantic models in backend/src/wrench/tools/windows_shortcuts/service.py.
export interface Shortcut {
  id: string
  keys: string[]
}

export interface ShortcutGroup {
  id: string
  shortcuts: Shortcut[]
}

export interface Catalog {
  groups: ShortcutGroup[]
  favorites: string[]
}
