import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import ProjectsTool from '../src/tools/projects/ProjectsTool.vue'
import type { Config, FolderEntry, ProjectEntry, State } from '../src/tools/projects/types'

const project = (name: string, rel: string, o: Partial<ProjectEntry> = {}): ProjectEntry => ({
  name,
  path: `C:\\Dev\\${rel}`,
  rel_path: rel,
  techs: ['Node'],
  is_template: false,
  ...o,
})
const folder = (name: string, rel: string, folders: FolderEntry[], projects: ProjectEntry[]): FolderEntry => ({
  name,
  path: `C:\\Dev\\${rel}`,
  rel_path: rel,
  project_count: projects.length,
  folders,
  projects,
})
const tree = folder('Dev', '', [folder('M3', 'M3', [], [project('Génération aspx', 'M3\\Génération aspx')])], [
  project('Alpha', 'Alpha'),
])

type Call = { action: string; payload?: Record<string, unknown> }
let calls: Call[]
let config: Config
let current: State
let picked: string | null
let app: App | null
let host: HTMLElement

const baseConfig: Config = { root: 'C:\\Dev', templates_dir: null, max_depth: 4, root_missing: false, templates_missing: false }
const baseState: State = {
  scanning: false,
  scan_error: null,
  git_available: true,
  tree,
  git: {},
  creation: null,
}

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      pick_folder: async () => ({ ok: true, data: picked }),
      get_app_icon: async () => ({ ok: true, data: null }),
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'get_config') return { ok: true, data: config }
        if (action === 'set_config') {
          config = { ...config, root: payload?.root as string }
          return { ok: true, data: config }
        }
        if (action === 'get_editors') {
          return {
            ok: true,
            data: [
              { id: 'vscode', name: 'VS Code', exe: 'code.exe', available: true },
              { id: 'ghost', name: 'Ghost', exe: 'ghost.exe', available: false },
            ],
          }
        }
        if (action === 'open_in') return { ok: true, data: null }
        return { ok: true, data: current }
      },
    },
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
const settle = async () => {
  await wait(20)
  await nextTick()
}
const button = (text: string) => [...host.querySelectorAll('button')].find((b) => b.textContent?.includes(text))

async function mountTool(): Promise<void> {
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(ProjectsTool).use(i18n)
  app.mount(host)
  await settle()
}

beforeEach(() => {
  calls = []
  config = { ...baseConfig }
  current = { ...baseState }
  picked = 'C:\\Dev'
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

describe('ProjectsTool', () => {
  it('sans racine, « Choose a folder » appelle pickFolder puis set_config', async () => {
    config = { ...baseConfig, root: null }
    current = { ...baseState, tree: null }
    await mountTool()
    button('Choose a folder')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'set_config')?.payload).toEqual({
      root: 'C:\\Dev',
      templates_dir: null,
      max_depth: 4,
    })
  })

  it('racine introuvable, parcours en cours et dossier vide', async () => {
    config = { ...baseConfig, root_missing: true }
    await mountTool()
    expect(host.textContent).toContain('The root folder was not found')
    app?.unmount()
    host.remove()
    config = { ...baseConfig }
    current = { ...baseState, scanning: true, tree: null }
    await mountTool()
    expect(host.textContent).toContain('Scanning')
    app?.unmount()
    host.remove()
    current = { ...baseState, tree: folder('Dev', '', [], []) }
    await mountTool()
    expect(host.textContent).toContain('This folder is empty')
  })

  it('une carte dossier entre dans le dossier, le fil d’Ariane remonte', async () => {
    await mountTool()
    expect(host.textContent).toContain('Alpha')
    button('M3')?.click()
    await settle()
    expect(host.textContent).toContain('Génération aspx')
    expect(host.textContent).not.toContain('Alpha')
    ;[...host.querySelectorAll('nav button')].find((b) => b.textContent?.includes('Dev'))?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await settle()
    expect(host.textContent).toContain('Alpha')
  })

  it('l’icône VS Code appelle open_in ; un éditeur introuvable est grisé', async () => {
    await mountTool()
    const vscode = host.querySelector('button[title="VS Code"]') as HTMLButtonElement
    vscode.click()
    await settle()
    expect(calls.find((c) => c.action === 'open_in')?.payload).toEqual({ path: 'C:\\Dev\\Alpha', editor_id: 'vscode' })
    const ghost = host.querySelector('button[title="Ghost: not found"]') as HTMLButtonElement
    expect(ghost.disabled).toBe(true)
  })

  it('la recherche remplace la grille et affiche le chemin relatif', async () => {
    await mountTool()
    const input = host.querySelector('input[type="search"]') as HTMLInputElement
    input.value = 'generation'
    input.dispatchEvent(new Event('input'))
    await settle()
    expect(host.textContent).toContain('Génération aspx')
    expect(host.textContent).toContain('M3\\Génération aspx')
    expect(host.textContent).not.toContain('Alpha')
    input.value = 'zzz'
    input.dispatchEvent(new Event('input'))
    await settle()
    expect(host.textContent).toContain('No project matches')
    input.value = ''
    input.dispatchEvent(new Event('input'))
    await settle()
    expect(host.textContent).toContain('Alpha')
  })

  it('load_status reçoit les projets visibles, à chaque changement de grille', async () => {
    await mountTool()
    expect(calls.filter((c) => c.action === 'load_status').map((c) => c.payload)).toEqual([{ paths: ['C:\\Dev\\Alpha'] }])
    button('M3')?.click()
    await settle()
    expect(calls.filter((c) => c.action === 'load_status').at(-1)?.payload).toEqual({ paths: ['C:\\Dev\\M3\\Génération aspx'] })
  })

  it('cliquer une carte la sélectionne', async () => {
    await mountTool()
    const card = [...host.querySelectorAll('[data-project]')].find((e) => e.getAttribute('data-project') === 'C:\\Dev\\Alpha') as HTMLElement
    card.click()
    await settle()
    expect(card.classList.contains('selected')).toBe(true)
  })
})

describe('ProjectsTool, projet modèle', () => {
  const withTemplate = (): void => {
    current = { ...baseState, tree: folder('Dev', '', [], [project('Tpl', 'Tpl', { is_template: true }), project('Alpha', 'Alpha')]) }
  }
  const editorButton = (name: string) =>
    [...host.querySelectorAll('[data-project]')]
      .find((e) => e.textContent?.includes(name))
      ?.querySelector('button[title="VS Code"]') as HTMLButtonElement

  it('confirmation d’abord ; Cancel n’appelle rien ; Confirm appelle open_in', async () => {
    withTemplate()
    await mountTool()
    editorButton('Tpl').click()
    await settle()
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain('This project is a template. Open it anyway?')
    expect(calls.some((c) => c.action === 'open_in')).toBe(false)
    button('Cancel')?.click()
    await settle()
    expect(host.querySelector('[role="dialog"]')).toBeNull()
    expect(calls.some((c) => c.action === 'open_in')).toBe(false)
    editorButton('Tpl').click()
    await settle()
    button('Confirm')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'open_in')?.payload).toEqual({ path: 'C:\\Dev\\Tpl', editor_id: 'vscode' })
    expect(host.querySelector('[role="dialog"]')).toBeNull()
  })

  it('un projet ordinaire s’ouvre sans confirmation', async () => {
    withTemplate()
    await mountTool()
    editorButton('Alpha').click()
    await settle()
    expect(host.querySelector('[role="dialog"]')).toBeNull()
    expect(calls.find((c) => c.action === 'open_in')?.payload).toEqual({ path: 'C:\\Dev\\Alpha', editor_id: 'vscode' })
  })
})

describe('ProjectsTool, carte', () => {
  it('affiche la branche d’un projet git et l’étiquette Template d’un modèle', async () => {
    current = {
      ...baseState,
      tree: folder('Dev', '', [], [project('Tpl', 'Tpl', { is_template: true }), project('Alpha', 'Alpha')]),
      git: { 'C:\\Dev\\Alpha': { branch: 'feature/x', running: null, error: null, staged: 0, unstaged: 0, untracked: 0, ahead: 0, conflicts: 0 } as never },
    }
    await mountTool()
    const card = (name: string) => [...host.querySelectorAll('[data-project]')].find((e) => e.textContent?.includes(name))
    expect(card('Alpha')?.textContent).toContain('feature/x')
    expect(card('Alpha')?.textContent).not.toContain('Template')
    expect(card('Tpl')?.textContent).toContain('Template')
  })

  it('un projet en erreur git affiche le badge d’erreur avec le message', async () => {
    current = {
      ...baseState,
      git: { 'C:\\Dev\\Alpha': { branch: null, running: null, error: { code: 'git_failed', message: 'boom' }, staged: 0, unstaged: 0, untracked: 0, ahead: 0, conflicts: 0 } as never },
    }
    await mountTool()
    const badge = host.querySelector('.badge.error')
    expect(badge?.textContent).toContain('read error')
    expect(badge?.getAttribute('title')).toContain('boom')
    expect(host.querySelector('.badge.clean')).toBeNull()
  })
})

describe('ProjectsTool, sondage', () => {
  const getStates = () => calls.filter((c) => c.action === 'get_state').length
  const mountFake = async (): Promise<void> => {
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(ProjectsTool).use(i18n)
    app.mount(host)
    await vi.advanceTimersByTimeAsync(0)
  }
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('ne tourne pas quand rien n’est en cours', async () => {
    await mountFake()
    await vi.advanceTimersByTimeAsync(3000)
    expect(getStates()).toBe(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('tourne pendant le parcours et s’arrête au démontage', async () => {
    current = { ...baseState, scanning: true, tree: null }
    await mountFake()
    await vi.advanceTimersByTimeAsync(2500)
    expect(getStates()).toBe(3)
    app?.unmount()
    app = null
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(3000)
    expect(getStates()).toBe(3)
  })
})
