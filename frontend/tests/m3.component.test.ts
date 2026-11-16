import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import M3Tool from '../src/tools/m3/M3Tool.vue'
import type { State } from '../src/tools/m3/types'

type Call = { action: string; payload?: Record<string, unknown> }
let calls: Call[]
let state: State
let app: App | null
let host: HTMLElement

function idleState(connected = false): State {
  return {
    config: {
      tenant: 'TEN_TST',
      eda_base_url: 'https://m3.example.com',
      company: '100',
      division: 'CF0',
      language: 'FR',
      output_dir: 'C:\\out',
    },
    connected: { eda: connected, mashup: false, xtend: false, workspaces: false },
    job: {
      kind: null,
      running: false,
      status: '',
      done: 0,
      total: 0,
      ok: 0,
      failed: 0,
      log: [],
      error: null,
      seq: 0,
    },
  }
}

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'get_state') return { ok: true, data: state }
        if (action === 'set_config') return { ok: true, data: payload }
        return { ok: true, data: null }
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
  app = createApp(M3Tool).use(i18n)
  app.mount(host)
  await flush()
}

function button(label: string, contains = ''): HTMLButtonElement {
  const found = [...host.querySelectorAll<HTMLButtonElement>('button')].find(
    (b) => b.textContent?.trim().startsWith(label) && b.textContent.includes(contains),
  )
  if (!found) throw new Error(`button ${label} not found`)
  return found
}

beforeEach(() => {
  calls = []
  state = idleState()
  setLanguage('en')
  installApi()
})

afterEach(() => {
  app?.unmount()
  host?.remove()
  app = null
})

describe('M3Tool', () => {
  it('shows the four tabs in order and loads the saved settings', async () => {
    await mountTool()
    const labels = [...host.querySelectorAll('[role="tab"]')].map((b) => b.textContent?.trim())
    expect(labels).toEqual(['EDA export', 'Mashups', 'Workspaces and widgets', 'Xtend code'])
    expect(host.querySelector<HTMLInputElement>('input')?.value).toBe('TEN_TST')
  })

  it('starts the Edge login of the EDA tab', async () => {
    await mountTool()
    button('Connect (Edge)').click()
    await flush()
    expect(calls).toContainEqual({ action: 'login', payload: { target: 'eda' } })
  })

  it('keeps the export disabled until connected and EDAs are given, then exports them', async () => {
    state = idleState(true)
    await mountTool()
    const exportButton = (): HTMLButtonElement => button('Export ', 'EDAs')
    expect(exportButton().disabled).toBe(true)

    const area = host.querySelector<HTMLTextAreaElement>('textarea')!
    area.value = 'EDA_1\nEDA_2\nEDA_1'
    area.dispatchEvent(new Event('input'))
    await flush()
    expect(exportButton().textContent?.trim()).toBe('Export 2 EDAs')

    exportButton().click()
    await flush()
    expect(calls).toContainEqual({ action: 'eda_export', payload: { edas: 'EDA_1\nEDA_2\nEDA_1' } })
  })
})
