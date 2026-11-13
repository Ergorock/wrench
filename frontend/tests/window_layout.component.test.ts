import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import WindowLayoutTool from '../src/tools/window_layout/WindowLayoutTool.vue'
import enTool from '../src/tools/window_layout/i18n/en.json'
import frTool from '../src/tools/window_layout/i18n/fr.json'

type Layout = { id: string; name: string; saved_at: string; windows: unknown[] }

let layouts: Layout[]
let restoreMissing: { exe: string; title: string }[]
let calls: { action: string; payload?: Record<string, unknown> }[]
let app: App | null
let host: HTMLElement

beforeEach(() => {
  layouts = [{ id: 'L1', name: 'Dev', saved_at: '2026-11-13T10:00', windows: [{}, {}] }]
  restoreMissing = []
  calls = []
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'list_windows') {
          return { ok: true, data: { windows: [{ exe: 'code.exe', title: 'main.py' }] } }
        }
        if (action === 'get_layouts') return { ok: true, data: { layouts } }
        if (action === 'save_layout') {
          layouts = [...layouts, { id: 'L2', name: String(payload?.name), saved_at: 'now', windows: [] }]
          return { ok: true, data: { layouts } }
        }
        if (action === 'restore_layout') {
          return { ok: true, data: { restored: 2, missing: restoreMissing } }
        }
        if (action === 'delete_layout') {
          layouts = layouts.filter((l) => l.id !== payload?.layout_id)
          return { ok: true, data: { layouts } }
        }
        throw new Error(`unexpected ${action}`)
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
  app = createApp(WindowLayoutTool).use(i18n)
  app.mount(host)
  await flush()
}

const button = (label: string): HTMLButtonElement =>
  [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement

describe('WindowLayoutTool', () => {
  it('affiche les fenêtres ouvertes et les dispositions enregistrées', async () => {
    await mountTool()
    expect(host.textContent).toContain('main.py')
    expect(host.querySelector('[data-layout="Dev"]')).not.toBeNull()
  })

  it('enregistre la disposition sous le nom saisi', async () => {
    await mountTool()
    const input = host.querySelector('input') as HTMLInputElement
    input.value = 'Réunion'
    input.dispatchEvent(new Event('input'))
    await nextTick()
    host.querySelector('form')!.dispatchEvent(new Event('submit'))
    await flush()
    expect(calls.at(-1)).toEqual({ action: 'save_layout', payload: { name: 'Réunion' } })
    expect(host.querySelector('[data-layout="Réunion"]')).not.toBeNull()
  })

  it('restaure une disposition et affiche le bilan, avec les programmes non ouverts', async () => {
    restoreMissing = [{ exe: 'firefox.exe', title: 'Mail' }]
    await mountTool()
    button(enTool.restore).click()
    await flush()
    expect(calls.some((c) => c.action === 'restore_layout')).toBe(true)
    expect(host.textContent).toContain(enTool.restored.replace('{count}', '2'))
    expect(host.textContent).toContain('firefox.exe')
  })

  it('demande une confirmation avant de supprimer une disposition', async () => {
    await mountTool()
    button(enTool.delete).click()
    await nextTick()
    expect(calls.some((c) => c.action === 'delete_layout')).toBe(false)
    button(enTool.confirmDelete).click()
    await flush()
    expect(calls.at(-1)).toEqual({ action: 'delete_layout', payload: { layout_id: 'L1' } })
    expect(host.querySelector('[data-layout="Dev"]')).toBeNull()
  })

  it('les textes FR et EN ont les mêmes clés', () => {
    expect(Object.keys(frTool).sort()).toEqual(Object.keys(enTool).sort())
  })
})
