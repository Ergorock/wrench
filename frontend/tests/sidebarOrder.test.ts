import { describe, expect, it } from 'vitest'
import { buildSidebar, isToolEnabled, resolveOrder } from '../src/shell/sidebarOrder'
import type { Category, Settings, SidebarSettings, ToolManifest } from '../src/bridge/types'

const CATS: Category[] = [
  { id: 'system', icon: 'monitor' },
  { id: 'productivity', icon: 'zap' },
  { id: 'development', icon: 'code' },
  { id: 'files', icon: 'folder' },
]

function tool(id: string, category: string, enabledByDefault = true): ToolManifest {
  return { id, category, icon: 'wrench', version: '1.0.0', enabled_by_default: enabledByDefault }
}

function settings(
  partial: Partial<Omit<Settings, 'sidebar'>> & { sidebar?: Partial<SidebarSettings> } = {},
): Settings {
  const { sidebar, ...rest } = partial
  return {
    schema_version: 1,
    language: 'fr',
    theme: 'system',
    autostart: false,
    sidebar: { collapsed: false, category_order: [], tool_order: {}, favorites: [], ...sidebar },
    tools: {},
    window: { x: null, y: null, width: 1100, height: 720, maximized: false },
    updates: { auto_check: true, last_check: null },
    editors: [],
    last_tool: null,
    ...rest,
  }
}

describe('sidebarOrder', () => {
  it('resolveOrder ignore les inconnus et ajoute les nouveaux en fin', () => {
    expect(resolveOrder(['b', 'zzz', 'a'], ['a', 'b', 'c'])).toEqual(['b', 'a', 'c'])
  })

  it('resolveOrder dédoublonne', () => {
    expect(resolveOrder(['a', 'a'], ['a'])).toEqual(['a'])
  })

  it('isToolEnabled : réglage utilisateur sinon défaut du manifeste', () => {
    expect(isToolEnabled(tool('t', 'system', false), settings())).toBe(false)
    expect(isToolEnabled(tool('t', 'system', false), settings({ tools: { t: { enabled: true } } }))).toBe(true)
  })

  it('masque les catégories vides et les outils désactivés', () => {
    const m = buildSidebar(CATS, [tool('t1', 'system'), tool('t2', 'files')],
      settings({ tools: { t2: { enabled: false } } }))
    expect(m.categories.map((c) => c.category.id)).toEqual(['system'])
  })

  it('favoris filtrés sur les outils actifs, ordre conservé', () => {
    const m = buildSidebar(CATS, [tool('t1', 'system'), tool('t2', 'system'), tool('t3', 'system', false)],
      settings({ sidebar: { favorites: ['t2', 'gone', 't3', 't1'] } }))
    expect(m.favorites.map((t) => t.id)).toEqual(['t2', 't1'])
  })

  it("respecte l'ordre des catégories enregistré", () => {
    const m = buildSidebar(CATS, [tool('t1', 'system'), tool('t2', 'files')],
      settings({ sidebar: { category_order: ['files'] } }))
    expect(m.categories.map((c) => c.category.id)).toEqual(['files', 'system'])
  })

  it("respecte l'ordre des outils d'une catégorie, ignore les inconnus, ajoute les nouveaux en fin", () => {
    const m = buildSidebar(CATS, [tool('a', 'system'), tool('b', 'system'), tool('c', 'system')],
      settings({ sidebar: { tool_order: { system: ['c', 'gone', 'a'] } } }))
    expect(m.categories[0].tools.map((t) => t.id)).toEqual(['c', 'a', 'b'])
  })
})
