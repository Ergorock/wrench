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

let actions: string[]
let runningPolls: number
let app: App | null
let host: HTMLElement

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string) => {
        actions.push(action)
        if (action === 'get_config') {
          return { ok: true, data: { roots: ['C:\\Dev'], max_depth: 3, missing_roots: [] } }
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

beforeEach(() => {
  actions = []
  runningPolls = 1
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
  it('rescan puis fetch_all à l’ouverture, interroge get_state tant qu’une opération tourne', async () => {
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(GitReposTool).use(i18n)
    app.mount(host)
    await wait(20)
    await nextTick()
    expect(actions).toEqual(['get_config', 'rescan', 'fetch_all'])
    expect(host.textContent).toContain('Fetching…')
    await wait(2300)
    await nextTick()
    // One poll still running, one idle, then no more polling.
    expect(actions).toEqual(['get_config', 'rescan', 'fetch_all', 'get_state', 'get_state'])
    expect(host.textContent).toContain('↑1')
    expect(host.textContent).not.toContain('Fetching…')
  }, 10000)
})
