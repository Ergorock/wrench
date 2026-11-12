import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import en from '../src/i18n/en.json'
import { toasts } from '../src/shell/toasts'
import ShortcutsTool from '../src/tools/windows_shortcuts/ShortcutsTool.vue'
import enTool from '../src/tools/windows_shortcuts/i18n/en.json'
import frTool from '../src/tools/windows_shortcuts/i18n/fr.json'

const catalog = {
  groups: [
    {
      id: 'windows_snap',
      shortcuts: [
        { id: 'snap_left', keys: ['Win', 'Left'] },
        { id: 'snap_right', keys: ['Win', 'Right'] },
      ],
    },
    { id: 'capture', shortcuts: [{ id: 'screenshot_region', keys: ['Win', 'Shift', 'S'] }] },
  ],
  favorites: [] as string[],
}

type Call = { action: string; payload?: Record<string, unknown> }
let calls: Call[]
let favorites: string[]
let failSetFavorite: boolean
let app: App | null
let host: HTMLElement

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'get_catalog') return { ok: true, data: { ...catalog, favorites } }
        if (failSetFavorite) {
          return { ok: false, error: { code: 'unknown_shortcut', message: 'x' } }
        }
        const id = payload?.shortcut_id as string
        favorites = payload?.favorite ? [...favorites, id] : favorites.filter((f) => f !== id)
        return { ok: true, data: favorites }
      },
    },
  }
}

async function flush(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 10))
  await nextTick()
}

async function mountTool(): Promise<void> {
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(ShortcutsTool).use(i18n)
  app.mount(host)
  await flush()
}

function search(): HTMLInputElement {
  return host.querySelector('input') as HTMLInputElement
}

async function type(text: string): Promise<void> {
  search().value = text
  search().dispatchEvent(new Event('input'))
  await nextTick()
}

const rowIds = (): string[] =>
  [...host.querySelectorAll<HTMLElement>('[data-shortcut]')].map((r) => r.dataset.shortcut as string)

beforeEach(() => {
  calls = []
  favorites = []
  failSetFavorite = false
  installApi()
  setLanguage('en')
})

afterEach(() => {
  app?.unmount()
  app = null
  host?.remove()
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

describe('ShortcutsTool', () => {
  it('charge le catalogue, affiche les groupes et donne le focus à la recherche', async () => {
    await mountTool()
    expect(calls.map((c) => c.action)).toEqual(['get_catalog'])
    expect(rowIds()).toEqual(['snap_left', 'snap_right', 'screenshot_region'])
    expect(host.textContent).toContain(enTool.groups.windows_snap)
    expect(document.activeElement).toBe(search())
  })

  it('filtre en direct, ignore accents et casse, et accepte les noms de touche bruts en FR', async () => {
    setLanguage('fr')
    await mountTool()
    // « écran » apparaît dans les trois libellés français ; « ancrer » seulement dans deux.
    await type('ECRAN')
    expect(rowIds()).toEqual(['snap_left', 'snap_right', 'screenshot_region'])
    await type('ANCRER ecran')
    expect(rowIds()).toEqual(['snap_left', 'snap_right'])
    await type('win shift')
    expect(rowIds()).toEqual(['screenshot_region'])
    await type('   ')
    expect(rowIds()).toHaveLength(3)
    expect(host.textContent).toContain('Maj')
  })

  it('masque les groupes sans résultat et affiche noResults si rien ne correspond', async () => {
    await mountTool()
    await type('screenshot')
    expect(host.textContent).not.toContain(enTool.groups.windows_snap)
    await type('zzzzzz')
    expect(rowIds()).toEqual([])
    expect(host.textContent).toContain(enTool.noResults)
  })

  it('affiche la section Favoris en tête seulement s’il y a des favoris', async () => {
    favorites = ['snap_right']
    await mountTool()
    const headings = [...host.querySelectorAll('h2')].map((h) => h.textContent?.trim())
    expect(headings[0]).toBe(enTool.favorites)
    expect(rowIds()).toEqual(['snap_right', 'snap_left', 'snap_right', 'screenshot_region'])
    await type('screenshot')
    expect([...host.querySelectorAll('h2')].map((h) => h.textContent?.trim())).not.toContain(
      enTool.favorites,
    )
  })

  it('pas de section Favoris sans favori', async () => {
    await mountTool()
    expect([...host.querySelectorAll('h2')].map((h) => h.textContent?.trim())).not.toContain(
      enTool.favorites,
    )
  })

  it('l’étoile met à jour tout de suite puis appelle set_favorite', async () => {
    await mountTool()
    const star = host.querySelector<HTMLButtonElement>('[data-shortcut="snap_left"] button')!
    expect(star.getAttribute('aria-label')).toBe(enTool.pin)
    star.click()
    await nextTick()
    expect(host.querySelector('h2')?.textContent?.trim()).toBe(enTool.favorites)
    await flush()
    expect(calls.at(-1)).toEqual({
      action: 'set_favorite',
      payload: { shortcut_id: 'snap_left', favorite: true },
    })
    const again = host.querySelector<HTMLButtonElement>('[data-shortcut="snap_left"] button')!
    expect(again.getAttribute('aria-label')).toBe(enTool.unpin)
  })

  it('revient à l’état précédent si set_favorite échoue, sans second toast', async () => {
    await mountTool()
    failSetFavorite = true
    host.querySelector<HTMLButtonElement>('[data-shortcut="snap_left"] button')!.click()
    await flush()
    expect([...host.querySelectorAll('h2')].map((h) => h.textContent?.trim())).not.toContain(
      enTool.favorites,
    )
    // useTool shows exactly one toast; the tool must not add another.
    expect(toasts.value.map((t) => t.message)).toEqual([enTool.errors.unknown_shortcut])
  })

  describe('étoiles cliquées coup sur coup', () => {
    type Pending = { shortcutId: string; resolve: (res: unknown) => void }
    let pending: Pending[]

    // set_favorite calls wait until the test resolves them by hand.
    function installManualApi(): void {
      pending = []
      ;(window as unknown as { pywebview: unknown }).pywebview = {
        api: {
          tool_call: (_tool: string, action: string, payload?: Record<string, unknown>) =>
            action === 'get_catalog'
              ? Promise.resolve({ ok: true, data: catalog })
              : new Promise((resolve) =>
                  pending.push({ shortcutId: payload?.shortcut_id as string, resolve }),
                ),
        },
      }
    }

    const ok = (data: string[]) => ({ ok: true, data })
    const fail = { ok: false, error: { code: 'internal_error', message: 'x' } }
    const favoriteHeadings = (): number =>
      [...host.querySelectorAll('h2')].filter((h) => h.textContent?.trim() === enTool.favorites)
        .length
    const isFavorite = (id: string): boolean =>
      host.querySelectorAll(`[data-shortcut="${id}"]`).length === 2

    it('deux échecs successifs ne laissent aucun favori fantôme', async () => {
      installManualApi()
      await mountTool()
      host.querySelector<HTMLButtonElement>('[data-shortcut="snap_left"] button')!.click()
      host.querySelector<HTMLButtonElement>('[data-shortcut="snap_right"] button')!.click()
      await nextTick()
      expect(isFavorite('snap_left') && isFavorite('snap_right')).toBe(true)

      pending[0].resolve(fail)
      await flush()
      expect(isFavorite('snap_left')).toBe(false)
      expect(isFavorite('snap_right')).toBe(true) // still waiting for its answer

      pending[1].resolve(fail)
      await flush()
      expect(favoriteHeadings()).toBe(0)
      expect(toasts.value).toHaveLength(2)
    })

    it('garde le second favori affiché quand le premier est confirmé, sans clignotement', async () => {
      installManualApi()
      await mountTool()
      host.querySelector<HTMLButtonElement>('[data-shortcut="snap_left"] button')!.click()
      host.querySelector<HTMLButtonElement>('[data-shortcut="snap_right"] button')!.click()
      await nextTick()

      pending[0].resolve(ok(['snap_left']))
      await flush()
      expect(isFavorite('snap_left')).toBe(true)
      expect(isFavorite('snap_right')).toBe(true)

      pending[1].resolve(ok(['snap_left', 'snap_right']))
      await flush()
      expect(isFavorite('snap_left') && isFavorite('snap_right')).toBe(true)
    })

    it('envoie les appels set_favorite l’un après l’autre, dans l’ordre des clics', async () => {
      installManualApi()
      await mountTool()
      host.querySelector<HTMLButtonElement>('[data-shortcut="snap_left"] button')!.click()
      host.querySelector<HTMLButtonElement>('[data-shortcut="snap_right"] button')!.click()
      await flush()
      expect(pending.map((p) => p.shortcutId)).toEqual(['snap_left'])

      pending[0].resolve(ok(['snap_left']))
      await flush()
      expect(pending.map((p) => p.shortcutId)).toEqual(['snap_left', 'snap_right'])
      pending[1].resolve(ok(['snap_left', 'snap_right']))
      await flush()
    })
  })

  it('Ctrl+F redonne le focus à la recherche et sélectionne son texte', async () => {
    await mountTool()
    await type('win')
    ;(document.activeElement as HTMLElement).blur()
    const event = new KeyboardEvent('keydown', { key: 'f', ctrlKey: true, cancelable: true })
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(search())
    expect(search().selectionStart).toBe(0)
    expect(search().selectionEnd).toBe(3)
  })

  it('retire l’écouteur keydown au démontage', async () => {
    const remove = vi.spyOn(window, 'removeEventListener')
    await mountTool()
    app?.unmount()
    app = null
    expect(remove.mock.calls.some(([type]) => type === 'keydown')).toBe(true)
    remove.mockRestore()
  })

  it('recalcule les libellés quand la langue change', async () => {
    await mountTool()
    expect(host.textContent).toContain(enTool.shortcuts.snap_left)
    setLanguage('fr')
    await nextTick()
    expect(host.textContent).toContain(frTool.shortcuts.snap_left)
    expect(host.textContent).not.toContain(en.home.title)
  })
})
