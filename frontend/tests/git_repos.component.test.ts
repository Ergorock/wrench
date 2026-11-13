import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import GitReposTool from '../src/tools/git_repos/GitReposTool.vue'
import type { RepoView } from '../src/tools/git_repos/types'

const repo = (o: Partial<RepoView> = {}): RepoView => ({
  path: 'C:\\Dev\\a',
  root: 'C:\\Dev',
  name: 'a',
  rel_path: 'a',
  web_url: 'https://github.com/x/a',
  branch: 'main',
  detached: false,
  upstream: 'origin/main',
  ahead: 0,
  behind: 0,
  staged: 0,
  unstaged: 0,
  untracked: 0,
  conflicts: 0,
  operation: null,
  remote_url: 'https://github.com/x/a',
  host: 'github',
  last_fetch: null,
  changed_files: [],
  running: null,
  error: null,
  ...o,
})

type Call = { action: string; payload?: Record<string, unknown> }
let calls: Call[]
let runningPolls: number
let failingPolls: number
let releaseRescan: (() => void) | null
let holdRescan: boolean
let app: App | null
let host: HTMLElement

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'get_config') {
          return { ok: true, data: { roots: ['C:\\Dev'], max_depth: 3, missing_roots: [] } }
        }
        if (action === 'get_branches') {
          return {
            ok: true,
            data: {
              main: 'main',
              local: [
                { name: 'feature/x', current: true, upstream: null, ahead: 0, behind: 0, merged: false, commits_not_in_main: 2, last_commit: null },
                { name: 'done', current: false, upstream: null, ahead: 0, behind: 0, merged: true, commits_not_in_main: 0, last_commit: null },
              ],
              remote: [{ name: 'origin/main', last_commit: null }],
            },
          }
        }
        if (action === 'get_commits') {
          const c = { short_hash: 'abc1234', hash: 'abc1234'.padEnd(40, '0'), subject: 'Fix it', message: 'Fix it\n\nbody', author: 'Ann', date: '2026-11-12T10:00:00Z', unpushed: true }
          return { ok: true, data: [c] }
        }
        if (action === 'rescan' && holdRescan) {
          await new Promise<void>((resolve) => (releaseRescan = resolve))
        }
        if (action === 'get_state' && failingPolls-- > 0) {
          return { ok: false, error: { code: 'internal_error', message: 'x' } }
        }
        // fetch_all starts a fetch; get_state reports it running `runningPolls` more times.
        const running = action === 'fetch_all' || (action === 'get_state' && runningPolls-- > 0)
        return {
          ok: true,
          data: { git_available: true, repos: [repo({ running: running ? 'fetch' : null, ahead: 1 })] },
        }
      },
    },
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

async function mountTool(): Promise<void> {
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(GitReposTool).use(i18n)
  app.mount(host)
  await wait(20)
  await nextTick()
}

beforeEach(() => {
  calls = []
  runningPolls = 1
  failingPolls = 0
  holdRescan = false
  releaseRescan = null
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

describe('GitReposTool', () => {
  it('rescan puis fetch_all automatique à l’ouverture, interroge get_state tant qu’une opération tourne', async () => {
    await mountTool()
    expect(calls.map((c) => c.action)).toEqual(['get_config', 'rescan', 'fetch_all'])
    expect(calls[2].payload).toEqual({ auto: true })
    expect(host.textContent).toContain('Fetching…')
    await wait(2300)
    await nextTick()
    // One poll still running, one idle, then no more polling.
    expect(calls.map((c) => c.action)).toEqual(['get_config', 'rescan', 'fetch_all', 'get_state', 'get_state'])
    expect(host.textContent).toContain('↑1')
    expect(host.textContent).not.toContain('Fetching…')
  }, 10000)

  it('« Tout récupérer » est interactif (sans auto)', async () => {
    runningPolls = 0
    await mountTool()
    await wait(1200)
    const button = [...host.querySelectorAll('button')].find((b) => b.textContent?.includes('Fetch all'))
    button?.click()
    await wait(20)
    expect(calls.filter((c) => c.action === 'fetch_all').map((c) => c.payload)).toEqual([{ auto: true }, {}])
  }, 10000)

  it('affiche un indicateur pendant la première découverte', async () => {
    holdRescan = true
    await mountTool()
    expect(host.textContent).toContain('Looking for repositories…')
    releaseRescan?.()
    await wait(20)
    await nextTick()
    expect(host.textContent).not.toContain('Looking for repositories…')
  })

  it('un seul toast quand get_state échoue pendant l’interrogation', async () => {
    failingPolls = 3
    await mountTool()
    await wait(3500)
    await nextTick()
    expect(calls.filter((c) => c.action === 'get_state').length).toBeGreaterThanOrEqual(3)
    expect(toasts.value).toHaveLength(1)
  }, 10000)

  it('Historique, ↑n et branche ouvrent les fenêtres ; Échap les ferme', async () => {
    runningPolls = 0
    await mountTool()
    const button = (text: string) => [...host.querySelectorAll('button')].find((b) => b.textContent?.includes(text))
    const press = async (el: Element | null | undefined, key?: string) => {
      if (key) el?.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
      else (el as HTMLElement | null)?.click()
      await wait(20)
      await nextTick()
    }

    await press(button('History'))
    expect(calls.at(-1)).toEqual({ action: 'get_commits', payload: { path: repo().path, ref: null, skip: 0 } })
    const dialog = host.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('abc1234')
    expect(dialog?.querySelector('li')?.getAttribute('title')).toBe('Fix it\n\nbody')
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Close')
    await press(document.activeElement, 'Escape')
    expect(host.querySelector('[role="dialog"]')).toBeNull()

    await press(button('↑1'))
    expect(calls.at(-1)?.action).toBe('get_commits')
    await press(host.querySelector('[role="dialog"] .close'))

    await press(button('main'))
    expect(calls.at(-1)).toEqual({ action: 'get_branches', payload: { path: repo().path } })
    const branches = host.querySelector('[role="dialog"]')
    expect(branches?.textContent).toContain('+2 commits')
    expect(branches?.textContent).toContain('✓ merged')
    expect(branches?.textContent).toContain('Remote (1)')
    await press(button('feature/x'))
    expect(calls.at(-1)).toEqual({ action: 'get_commits', payload: { path: repo().path, ref: 'feature/x', skip: 0 } })
    expect(host.querySelectorAll('[role="dialog"]')).toHaveLength(2)
    await press(document.activeElement, 'Escape')
    expect(host.querySelectorAll('[role="dialog"]')).toHaveLength(1)
  })

  it('infobulles de l’icône d’hôte et de la branche', async () => {
    runningPolls = 0
    await mountTool()
    expect(host.querySelector('.host')?.getAttribute('title')).toBe('GitHub repository — github.com/x/a')
    expect(host.querySelector('.branch')?.getAttribute('title')).toContain('tracks origin/main')
  })
})
