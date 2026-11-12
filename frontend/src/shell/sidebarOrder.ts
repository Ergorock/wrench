import type { Category, Settings, ToolManifest } from '../bridge/types'

export interface SidebarModel {
  favorites: ToolManifest[]
  categories: { category: Category; tools: ToolManifest[] }[]
}

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

  return { favorites, categories: result }
}
