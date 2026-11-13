import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import QuickReferenceTool from '../src/tools/quick_reference/QuickReferenceTool.vue'
import enTool from '../src/tools/quick_reference/i18n/en.json'
import frTool from '../src/tools/quick_reference/i18n/fr.json'
import { toasts } from '../src/shell/toasts'

const reference = {
  sheets: [
    {
      id: 'git',
      entries: [
        { id: 'git_status', command: 'git status -sb' },
        { id: 'git_stash_pop', command: 'git stash pop' },
      ],
    },
    {
      id: 'sql',
      entries: [{ id: 'sql_distinct', command: 'SELECT DISTINCT colonne FROM table' }],
    },
  ],
}

let calls: string[]
let failLoad: boolean
let app: App | null
let host: HTMLElement

beforeEach(() => {
  calls = []
  failLoad = false
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string) => {
        calls.push(action)
        if (failLoad) return { ok: false, error: { code: 'internal_error', message: 'x' } }
        return { ok: true, data: reference }
      },
    },
  }
  setLanguage('en')
})

afterEach(() => {
  app?.unmount()
  app = null
  host?.remove()
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

async function flush(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 10))
  await nextTick()
}

async function mountTool(): Promise<void> {
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(QuickReferenceTool).use(i18n)
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

const entryIds = (): string[] =>
  [...host.querySelectorAll<HTMLElement>('[data-entry]')].map((r) => r.dataset.entry as string)

describe('QuickReferenceTool', () => {
  it('charge les fiches et affiche chaque commande avec sa description', async () => {
    await mountTool()
    expect(calls).toEqual(['get_sheets'])
    expect(entryIds()).toEqual(['git_status', 'git_stash_pop', 'sql_distinct'])
    expect(host.textContent).toContain(enTool.entries.git_status)
    expect(host.querySelector('[data-entry="git_status"] code')?.textContent).toBe('git status -sb')
  })

  it('filtre sur la description et sur la commande, sans tenir compte de la casse', async () => {
    await mountTool()
    await type('STASH')
    expect(entryIds()).toEqual(['git_stash_pop'])
    await type('distinct colonne')
    expect(entryIds()).toEqual(['sql_distinct'])
    await type('   ')
    expect(entryIds()).toHaveLength(3)
  })

  it('masque les fiches sans résultat et affiche noResults si rien ne correspond', async () => {
    await mountTool()
    await type('zzzzzz')
    expect(entryIds()).toEqual([])
    expect(host.textContent).toContain(enTool.noResults)
    expect(host.textContent).not.toContain(enTool.sheets.git)
  })

  it('recalcule les descriptions quand la langue change', async () => {
    await mountTool()
    setLanguage('fr')
    await nextTick()
    expect(host.textContent).toContain(frTool.entries.git_status)
    expect(host.textContent).not.toContain(enTool.entries.git_status)
  })

  it('reste vide sans erreur de rendu si le chargement échoue, avec un seul toast', async () => {
    failLoad = true
    await mountTool()
    expect(entryIds()).toEqual([])
    expect(toasts.value).toHaveLength(1)
  })
})
