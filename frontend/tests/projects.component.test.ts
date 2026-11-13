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
let setBuildGate: Promise<void> | null
let build: { command: string | null; suggested: string | null }
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
        if (action === 'open_in' || action === 'open_terminal' || action === 'run_build') return { ok: true, data: null }
        if (action === 'get_build') return { ok: true, data: build }
        if (action === 'set_build' && setBuildGate) await setBuildGate
        if (action === 'set_build') return { ok: true, data: { command: payload?.command, suggested: build.suggested } }
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
  build = { command: null, suggested: 'npm run build' }
  setBuildGate = null
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

describe('ProjectsTool, fiche du projet', () => {
  const A = 'C:\\Dev\\Alpha'
  const gitView = (o: Record<string, unknown> = {}) =>
    ({ path: A, name: 'Alpha', branch: 'main', running: null, error: null, staged: 0, unstaged: 0, untracked: 0, ahead: 0, conflicts: 0, remote_url: null, changed_files: [], ...o }) as never
  const select = async (name = 'Alpha') => {
    const card = [...host.querySelectorAll('[data-project]')].find((e) => e.textContent?.includes(name)) as HTMLElement
    card.click()
    await settle()
  }
  const panel = () => host.querySelector('[data-slot="detail"]')
  const panelButton = (text: string) => [...(panel()?.querySelectorAll('button') ?? [])].find((b) => b.textContent?.includes(text))
  const escape = async () => {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await settle()
  }

  it('absente sans sélection ; une carte l’ouvre, ✕ et Échap la ferment', async () => {
    await mountTool()
    expect(panel()).toBeNull()
    await select()
    expect(panel()?.textContent).toContain(A)
    ;(panel()?.querySelector('button[aria-label="Close"]') as HTMLButtonElement).click()
    await settle()
    expect(panel()).toBeNull()
    await select()
    await escape()
    expect(panel()).toBeNull()
  })

  it('Ouvrir : éditeur disponible, éditeur grisé, Terminal', async () => {
    await mountTool()
    await select()
    expect((panelButton('Ghost') as HTMLButtonElement).disabled).toBe(true)
    panelButton('VS Code')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'open_in')?.payload).toEqual({ path: A, editor_id: 'vscode' })
    panelButton('Terminal')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'open_terminal')?.payload).toEqual({ path: A })
  })

  it('sur un modèle, Terminal demande la confirmation ; Cancel n’appelle rien', async () => {
    current = { ...baseState, tree: folder('Dev', '', [], [project('Tpl', 'Tpl', { is_template: true })]) }
    await mountTool()
    await select('Tpl')
    panelButton('Terminal')?.click()
    await settle()
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain('template')
    await escape()
    expect(panel()).not.toBeNull()
    expect(calls.some((c) => c.action === 'open_terminal')).toBe(false)
    button('Cancel')?.click()
    await settle()
    expect(calls.some((c) => c.action === 'open_terminal')).toBe(false)
    panelButton('Terminal')?.click()
    await settle()
    button('Confirm')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'open_terminal')?.payload).toEqual({ path: 'C:\\Dev\\Tpl' })
  })

  it('Commit… ouvre CommitDialog et l’envoi appelle commit', async () => {
    current = { ...baseState, git: { [A]: gitView({ remote_url: 'https://github.com/a/b.git', changed_files: ['a.txt'], unstaged: 1 }) } }
    await mountTool()
    await select()
    panelButton('Commit…')?.click()
    await settle()
    const area = host.querySelector('textarea') as HTMLTextAreaElement
    area.value = 'fix'
    area.dispatchEvent(new Event('input'))
    await settle()
    button('Commit and push')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'commit')?.payload).toEqual({ path: A, message: 'fix', push: true })
  })

  it('Associer un dépôt… seulement sans remote_url ; l’envoi appelle set_remote', async () => {
    current = { ...baseState, git: { [A]: gitView() } }
    await mountTool()
    await select()
    expect(panelButton('Open the repository')).toBeUndefined()
    panelButton('Link a repository…')?.click()
    await settle()
    const input = host.querySelector('[role="dialog"] input') as HTMLInputElement
    input.value = 'https://github.com/a/b.git'
    input.dispatchEvent(new Event('input'))
    await settle()
    ;(host.querySelector('[role="dialog"] button[type="submit"]') as HTMLButtonElement).click()
    await settle()
    expect(calls.find((c) => c.action === 'set_remote')?.payload).toEqual({ path: A, url: 'https://github.com/a/b.git' })
  })

  it('avec remote_url : Ouvrir le dépôt appelle open_repo_page', async () => {
    current = { ...baseState, git: { [A]: gitView({ remote_url: 'https://github.com/a/b.git' }) } }
    await mountTool()
    await select()
    expect(panelButton('Link a repository…')).toBeUndefined()
    panelButton('Open the repository')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'open_repo_page')?.payload).toEqual({ path: A })
  })

  it('affiche l’erreur git du projet', async () => {
    current = { ...baseState, git: { [A]: gitView({ error: { code: 'git_failed', message: 'boom' } }) } }
    await mountTool()
    await select()
    expect(panel()?.textContent).not.toContain('boom')
    expect(panel()?.querySelector('[title="boom"]')?.textContent).toContain('Something went wrong.')
  })

  it('Build : suggestion en placeholder, Entrée appelle set_build, Lancer appelle run_build', async () => {
    await mountTool()
    await select()
    const input = panel()?.querySelector('input.build') as HTMLInputElement
    expect(input.placeholder).toBe('npm run build')
    expect(input.value).toBe('')
    input.value = 'npm run build'
    input.dispatchEvent(new Event('input'))
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await settle()
    expect(calls.filter((c) => c.action === 'set_build').map((c) => c.payload)).toEqual([{ path: A, command: 'npm run build' }])
    panelButton('Run')?.click()
    await settle()
    expect(calls.find((c) => c.action === 'run_build')?.payload).toEqual({ path: A })
  })

  it('projet disparu après un rescan : la fiche reste avec une erreur, sans actions ni load_status', async () => {
    await mountTool()
    await select()
    const before = calls.filter((c) => c.action === 'load_status').length
    current = { ...baseState, tree: folder('Dev', '', [], []) }
    button('Refresh')?.click()
    await settle()
    expect(panel()?.textContent).toContain('no longer exists')
    expect(panelButton('Terminal')).toBeUndefined()
    expect(calls.filter((c) => c.action === 'load_status').length).toBe(before)
  })
})

describe('ProjectsTool, fiche : build en attente', () => {
  const A = 'C:\\Dev\\Alpha'
  const open = async () => {
    await mountTool()
    ;(host.querySelector('[data-project]') as HTMLElement).click()
    await settle()
    const input = host.querySelector('[data-slot="detail"] input.build') as HTMLInputElement
    input.value = 'make'
    input.dispatchEvent(new Event('input'))
    return input
  }
  const run = () => [...host.querySelectorAll('[data-slot="detail"] button')].find((b) => b.textContent?.includes('Run')) as HTMLButtonElement

  it('Lancer attend la fin de l’enregistrement : set_build puis run_build', async () => {
    let release!: () => void
    setBuildGate = new Promise<void>((r) => (release = r))
    const input = await open()
    input.dispatchEvent(new Event('blur'))
    run().click()
    await settle()
    expect(calls.some((c) => c.action === 'set_build')).toBe(true)
    expect(calls.some((c) => c.action === 'run_build')).toBe(false)
    release()
    await settle()
    const order = calls.map((c) => c.action).filter((a) => a === 'set_build' || a === 'run_build')
    expect(order).toEqual(['set_build', 'run_build'])
    expect(calls.find((c) => c.action === 'set_build')?.payload).toEqual({ path: A, command: 'make' })
  })

  it('si l’enregistrement échoue, run_build n’est jamais appelé', async () => {
    let fail!: () => void
    setBuildGate = new Promise<void>((_r, rej) => (fail = () => rej(new Error('x'))))
    const input = await open()
    input.dispatchEvent(new Event('blur'))
    run().click()
    await settle()
    fail()
    await settle()
    expect(calls.some((c) => c.action === 'run_build')).toBe(false)
  })
})
