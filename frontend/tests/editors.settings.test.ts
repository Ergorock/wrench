import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import fr from '../src/i18n/fr.json'
import { appIcon } from '../src/shell/appIcons'
import SettingsView from '../src/shell/components/SettingsView.vue'
import { useShell } from '../src/shell/state'
import { toasts } from '../src/shell/toasts'

const EDITORS = [
  { id: 'claude', name: 'Claude', exe: 'claude.exe', args: ['{path}'] },
  { id: 'kiro', name: 'Kiro', exe: 'kiro.exe', args: ['{path}'] },
  { id: 'vscode', name: 'VS Code', exe: 'code.exe', args: ['{path}'] },
]

let app: App | null
let host: HTMLElement
let saved: { editors: { id: string; name: string; exe: string; args: string[] }[] }[]
let iconCalls: string[]

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      get_bootstrap: async () => ({
        ok: true,
        data: {
          settings: {
            schema_version: 1,
            language: 'fr',
            theme: 'light',
            autostart: false,
            sidebar: { collapsed: false, category_order: [], tool_order: {}, favorites: [] },
            tools: {},
            window: { x: null, y: null, width: 1100, height: 720, maximized: false },
            updates: { auto_check: true, last_check: null },
            editors: EDITORS,
            last_tool: null,
          },
          categories: [],
          tools: [],
          autostart: { available: false, enabled: false },
          warnings: [],
        },
      }),
      save_settings: async (s: (typeof saved)[number]) => (saved.push(s), { ok: true, data: s }),
      get_app_icon: async (exe: string) => (iconCalls.push(exe), { ok: true, data: null }),
      get_update_status: async () => ({
        ok: true,
        data: { supported: false, current_version: '1.0.0', status: 'idle', info: null, progress: 0, error_code: null },
      }),
      pick_exe: async () => ({ ok: true, data: 'C:\Apps\mon.exe' }),
    },
  }
}

async function flush(): Promise<void> {
  for (let i = 0; i < 5; i++) await nextTick()
  await new Promise((r) => setTimeout(r, 0))
}

beforeEach(async () => {
  saved = []
  iconCalls = []
  setLanguage('fr')
  installApi()
  await useShell().init()
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(SettingsView).use(i18n)
  app.mount(host)
  await flush()
})

afterEach(() => {
  app?.unmount()
  host.remove()
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

const rows = () => host.querySelectorAll('[data-testid="editor-row"]')
const button = (label: string, within: ParentNode = host) =>
  [...within.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement

describe('section Éditeurs', () => {
  it('affiche une ligne par éditeur des paramètres', () => {
    expect(rows()).toHaveLength(3)
    expect(rows()[0].textContent).toContain('Claude')
    expect(rows()[1].textContent).toContain('kiro.exe')
  })

  it('« ↓ » sur la première ligne enregistre le nouvel ordre', async () => {
    button('↓', rows()[0]).click()
    await flush()
    expect(saved.at(-1)?.editors.map((e) => e.id)).toEqual(['kiro', 'claude', 'vscode'])
  })

  it('l’ajout de « Mon Éditeur » enregistre un id slug et args ["{path}"]', async () => {
    button(fr.settings.editors.add).click()
    await flush()
    const inputs = host.querySelectorAll<HTMLInputElement>('.editor-form input')
    inputs[0].value = 'Mon Éditeur'
    inputs[0].dispatchEvent(new Event('input'))
    inputs[1].value = 'mon.exe'
    inputs[1].dispatchEvent(new Event('input'))
    await flush()
    button(fr.settings.editors.save, host.querySelector('.editor-form') as HTMLElement).click()
    await flush()
    const added = saved.at(-1)?.editors.at(-1)
    expect(added).toEqual({ id: 'mon-editeur', name: 'Mon Éditeur', exe: 'mon.exe', args: ['{path}'] })
  })
})

describe('appIcon', () => {
  it('un seul appel au pont par exécutable', async () => {
    const a = appIcon('a.exe')
    const b = appIcon('a.exe')
    await flush()
    expect(a).toBe(b)
    expect(iconCalls.filter((e) => e === 'a.exe')).toHaveLength(1)
  })
})
