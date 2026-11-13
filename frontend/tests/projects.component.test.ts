import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import ProjectsTool from '../src/tools/projects/ProjectsTool.vue'
import type { Config, FolderEntry, ProjectEntry, Requirement, RequirementsView, State } from '../src/tools/projects/types'

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
let reqViews: RequirementsView[]
let reqFail = false
let reqChecked = false
let templates: string[]
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
        if (action === 'check_requirements' || action === 'get_requirements') {
          if (action === 'check_requirements') reqChecked = true
          if (!reqChecked) return { ok: true, data: { running: false, items: null, error: null } }
          if (reqFail) return { ok: false, error: { code: 'boom', message: 'down' } }
          return { ok: true, data: reqViews.length > 1 ? reqViews.shift() : reqViews[0] }
        }
        if (action === 'clear_creation') return { ok: true, data: { ...current, creation: null } }
        if (action === 'list_templates') return { ok: true, data: templates }
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
  templates = ['Basic', 'Node app']
  reqViews = [{ running: false, items: null, error: null }]
  reqFail = false
  reqChecked = false
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
    expect(panel()?.querySelector('[title="boom"]')?.textContent).toContain('The git command failed.')
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

describe('ProjectsTool, fiche : prérequis', () => {
  const A = 'C:\\Dev\\Alpha'
  const panel = () => host.querySelector('[data-slot="detail"]') as HTMLElement
  const verify = () => [...panel().querySelectorAll('button')].find((b) => b.textContent?.includes('Check')) as HTMLButtonElement
  const getReqs = () => calls.filter((c) => c.action === 'get_requirements').length
  const mountFake = async (): Promise<void> => {
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(ProjectsTool).use(i18n)
    app.mount(host)
    await vi.advanceTimersByTimeAsync(0)
    ;(host.querySelector('[data-project]') as HTMLElement).click()
    await vi.advanceTimersByTimeAsync(0)
  }
  const item = (tool: string, status: Requirement['status'], o: Record<string, unknown> = {}) => ({
    tool,
    required: null,
    installed: null,
    status,
    source: 'package.json',
    ...o,
  })

  it('Vérifier appelle check_requirements, puis les lignes affichent état, contrainte, version et source', async () => {
    reqViews = [
      { running: true, items: null, error: null },
      {
        running: false,
        items: [
          item('Node', 'ok', { required: '>=18', installed: '20.1.0' }),
          item('Python', 'missing', { required: '3.12', source: 'pyproject.toml' }),
        ],
        error: null,
      },
    ]
    await mountTool()
    ;(host.querySelector('[data-project]') as HTMLElement).click()
    await settle()
    verify().click()
    await wait(1100)
    await nextTick()
    expect(calls.find((c) => c.action === 'check_requirements')?.payload).toEqual({ path: A })
    const rows = [...panel().querySelectorAll('[data-requirement]')]
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toContain('Node')
    expect(rows[0].textContent).toContain('>=18')
    expect(rows[0].textContent).toContain('20.1.0')
    expect(rows[0].textContent).toContain('OK')
    expect(rows[0].getAttribute('title')).toBe('package.json')
    expect(rows[1].textContent).toContain('Python')
    expect(rows[1].textContent).toContain('Missing')
    expect(rows[1].getAttribute('title')).toBe('pyproject.toml')
  })

  it('liste vide : Aucun prérequis détecté', async () => {
    reqViews = [{ running: false, items: [], error: null }]
    await mountTool()
    ;(host.querySelector('[data-project]') as HTMLElement).click()
    await settle()
    verify().click()
    await settle()
    expect(panel().textContent).toContain('No requirement detected')
  })

  it('erreur de vérification : traduction par code, repli générique', async () => {
    reqViews = [{ running: false, items: null, error: { code: 'busy', message: 'x' } }]
    await mountTool()
    ;(host.querySelector('[data-project]') as HTMLElement).click()
    await settle()
    verify().click()
    await settle()
    expect(panel().textContent).toContain('An operation is already running')
    reqViews = [{ running: false, items: null, error: { code: 'nope', message: 'x' } }]
    verify().click()
    await settle()
    expect(panel().textContent).toContain('Something went wrong.')
  })

  describe('sondage', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('sonde toutes les secondes pendant running, puis s’arrête ; plus de minuterie au démontage', async () => {
      reqViews = [{ running: true, items: null, error: null }]
      await mountFake()
      verify().click()
      await vi.advanceTimersByTimeAsync(0)
      const base = getReqs()
      await vi.advanceTimersByTimeAsync(2500)
      expect(getReqs()).toBe(base + 2)
      reqViews = [{ running: false, items: [], error: null }]
      await vi.advanceTimersByTimeAsync(1000)
      const done = getReqs()
      await vi.advanceTimersByTimeAsync(3000)
      expect(getReqs()).toBe(done)
      reqViews = [{ running: true, items: null, error: null }]
      verify().click()
      await vi.advanceTimersByTimeAsync(0)
      app?.unmount()
      app = null
      expect(vi.getTimerCount()).toBe(0)
    })

    it('un seul toast par série d’échecs', async () => {
      reqViews = [{ running: true, items: null, error: null }]
      await mountFake()
      verify().click()
      await vi.advanceTimersByTimeAsync(0)
      reqFail = true
      await vi.advanceTimersByTimeAsync(3500)
      expect(toasts.value).toHaveLength(1)
    })
  })
})

describe('ProjectsTool, nouveau projet', () => {
  const dialog = () => host.querySelector('[role="dialog"]') as HTMLElement | null
  const type = async (el: HTMLInputElement, value: string) => {
    el.value = value
    el.dispatchEvent(new Event('input'))
    await settle()
  }
  const submit = () => dialog()?.querySelector('button[type="submit"]') as HTMLButtonElement
  const open = async () => {
    button('New project')?.click()
    await settle()
  }
  const fields = () => ({
    name: dialog()?.querySelector('#projects-new-name') as HTMLInputElement,
    url: dialog()?.querySelector('#projects-new-url') as HTMLInputElement,
  })

  it('liste les modèles, affiche la destination en lecture seule', async () => {
    await mountTool()
    await open()
    expect(calls.some((c) => c.action === 'list_templates')).toBe(true)
    expect(dialog()?.textContent).toContain('Basic')
    expect(dialog()?.textContent).toContain('Node app')
    const dest = dialog()?.querySelector('[data-slot="destination"]') as HTMLInputElement
    expect(dest.value).toBe('Dev')
    expect(dest.readOnly).toBe(true)
  })

  it('le bouton reste inactif : nom vide, URL ftp://x', async () => {
    await mountTool()
    await open()
    expect(submit().disabled).toBe(true)
    await type(fields().name, 'New')
    expect(submit().disabled).toBe(false)
    await type(fields().url, 'ftp://x')
    expect(submit().disabled).toBe(true)
    await type(fields().url, 'https://github.com/a/b.git')
    expect(submit().disabled).toBe(false)
  })

  it('l’envoi appelle create_project avec modèle, nom, dossier courant et URL', async () => {
    await mountTool()
    ;(host.querySelector('.folder, [data-folder]') as HTMLElement | null)?.click()
    await settle()
    await open()
    ;(dialog()?.querySelector('input[type="radio"][value="Node app"]') as HTMLInputElement).click()
    await type(fields().name, ' New ')
    await type(fields().url, 'https://github.com/a/b.git')
    submit().click()
    await settle()
    expect(calls.find((c) => c.action === 'create_project')?.payload).toEqual({
      template: 'Node app',
      name: 'New',
      parent_rel: 'M3',
      remote_url: 'https://github.com/a/b.git',
    })
  })

  it('sans URL, remote_url vaut null', async () => {
    await mountTool()
    await open()
    await type(fields().name, 'New')
    submit().click()
    await settle()
    expect(calls.find((c) => c.action === 'create_project')?.payload).toMatchObject({ parent_rel: '', remote_url: null })
  })

  it('quand creation.created arrive : la fenêtre se ferme et le nouveau projet est sélectionné', async () => {
    const fresh = project('Fresh', 'Fresh')
    const created = { ...baseState, tree: { ...tree, projects: [...tree.projects, fresh], project_count: 3 } }
    await mountTool()
    await open()
    await type(fields().name, 'Fresh')
    current = { ...created, creation: { running: false, error: null, created: fresh.path } }
    submit().click()
    await settle()
    expect(dialog()).toBeNull()
    expect(host.querySelector('[data-slot="detail"]')?.textContent).toContain('Fresh')
    expect(calls.some((c) => c.action === 'clear_creation')).toBe(true)
  })

  it('une erreur de création garde la fenêtre ouverte et affiche un toast', async () => {
    toasts.value = []
    await mountTool()
    await open()
    await type(fields().name, 'Fresh')
    current = { ...baseState, creation: { running: false, error: { code: 'copy_failed', message: 'x' }, created: null } }
    submit().click()
    await settle()
    expect(dialog()).not.toBeNull()
    expect(toasts.value).toHaveLength(1)
  })
})
