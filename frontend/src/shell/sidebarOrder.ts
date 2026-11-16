import type { Category, Settings, ToolManifest } from '../bridge/types'

export interface SidebarModel {
  favorites: ToolManifest[]
  recents: ToolManifest[]
  categories: { category: Category; tools: ToolManifest[] }[]
}

export const RECENTS_MAX = 3

export function resolveOrder(saved: string[], known: string[]): string[] {
  const knownSet = new Set(known)
  const kept = [...new Set(saved)].filter((id) => knownSet.has(id))
  const keptSet = new Set(kept)
  return [...kept, ...known.filter((id) => !keptSet.has(id))]
}

export function isToolEnabled(tool: ToolManifest, settings: Settings): boolean {
  return settings.tools[tool.id]?.enabled ?? tool.enabled_by_default
}

export function buildSidebar(
  categories: Category[],
  tools: ToolManifest[],
  settings: Settings,
): SidebarModel {
  const { sidebar } = settings
  const active = tools.filter((t) => isToolEnabled(t, settings))
  const byId = new Map(active.map((t) => [t.id, t]))
  const catById = new Map(categories.map((c) => [c.id, c]))

  const orderedCats = resolveOrder(sidebar.category_order, categories.map((c) => c.id))
  const result: SidebarModel['categories'] = []
  for (const catId of orderedCats) {
    const ids = active
      .filter((t) => t.category === catId)
      .map((t) => t.id)
      .sort()
    const ordered = resolveOrder(sidebar.tool_order[catId] ?? [], ids)
    if (ordered.length === 0) continue
    result.push({
      category: catById.get(catId)!,
      tools: ordered.map((id) => byId.get(id)!),
    })
  }

  const favorites = sidebar.favorites
    .map((id) => byId.get(id))
    .filter((t): t is ToolManifest => t !== undefined)

  const recents = sidebar.recents
    .map((id) => byId.get(id))
    .filter((t): t is ToolManifest => t !== undefined && !sidebar.favorites.includes(t.id))
    .slice(0, RECENTS_MAX)

  return { favorites, recents, categories: result }
}

const fold = (s: string): string => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

/** True when every word of the query appears in the text, ignoring case and accents. */
export function matchesQuery(text: string, query: string): boolean {
  const haystack = fold(text)
  return fold(query)
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}
