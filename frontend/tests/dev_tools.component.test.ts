import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import DevToolsTool from '../src/tools/dev_tools/DevToolsTool.vue'

type Call = { action: string; payload?: Record<string, unknown> }
let calls: Call[]
let app: App | null
let host: HTMLElement

function installApi(): void {
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'convert_color') {
          return {
            ok: true,
            data: { hex: '#1E90FF', rgb: [30, 144, 255], hsl: [210, 100, 56] },
          }
        }
        if (action === 'format_json') return { ok: true, data: '{\n  "a": 1\n}' }
        return { ok: true, data: 'résultat' }
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
  app = createApp(DevToolsTool).use(i18n)
  app.mount(host)
  await flush()
}

function tab(label: string): HTMLButtonElement {
  const found = [...host.querySelectorAll<HTMLButtonElement>('[role="tab"]')].find(
    (b) => b.textContent?.trim() === label,
  )
  if (!found) throw new Error(`tab ${label} not found`)
  return found
}

beforeEach(() => {
  calls = []
  setLanguage('en')
  installApi()
})

afterEach(() => {
  app?.unmount()
  host?.remove()
  app = null
})

describe('DevToolsTool', () => {
  it('shows the four tabs in order', async () => {
    await mountTool()
    const labels = [...host.querySelectorAll('[role="tab"]')].map((b) => b.textContent?.trim())
    expect(labels).toEqual(['Encoding', 'Color', 'JSON', 'XML'])
  })

  it('converts the default color when the color tab is opened', async () => {
    await mountTool()
    tab('Color').click()
    await flush()
    expect(calls).toContainEqual({ action: 'convert_color', payload: { color: '#1E90FF' } })
    expect(host.textContent).toContain('rgb(30, 144, 255)')
    expect(host.textContent).toContain('hsl(210, 100%, 56%)')
  })

  it('formats JSON through the backend', async () => {
    await mountTool()
    tab('JSON').click()
    await flush()
    const input = host.querySelector<HTMLTextAreaElement>('#dev-tools-json-input')
    if (!input) throw new Error('input not found')
    input.value = '{"a":1}'
    input.dispatchEvent(new Event('input'))
    const format = [...host.querySelectorAll<HTMLButtonElement>('button')].find(
      (b) => b.textContent?.trim() === 'Format',
    )
    if (!format) throw new Error('format button not found')
    format.click()
    await flush()
    expect(calls).toContainEqual({ action: 'format_json', payload: { text: '{"a":1}', minify: false } })
    const output = host.querySelector<HTMLTextAreaElement>('#dev-tools-json-output')
    expect(output?.value).toBe('{\n  "a": 1\n}')
  })
})
