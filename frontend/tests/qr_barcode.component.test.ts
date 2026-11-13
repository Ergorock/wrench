import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import QrBarcodeTool from '../src/tools/qr_barcode/QrBarcodeTool.vue'
import enTool from '../src/tools/qr_barcode/i18n/en.json'
import frTool from '../src/tools/qr_barcode/i18n/fr.json'
import { toasts } from '../src/shell/toasts'

let calls: { action: string; payload?: Record<string, unknown> }[]
let folderPick: string | null
let app: App | null
let host: HTMLElement

beforeEach(() => {
  vi.useFakeTimers()
  calls = []
  folderPick = null
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'generate') return { ok: true, data: { svg: '<svg></svg>' } }
        if (action === 'export') {
          return { ok: true, data: { path: `${payload?.folder}/${payload?.name}.svg` } }
        }
        throw new Error(`unexpected ${action}`)
      },
      pick_folder: async () => ({ ok: true, data: folderPick }),
    },
  }
  setLanguage('en')
})

afterEach(() => {
  vi.useRealTimers()
  app?.unmount()
  app = null
  host?.remove()
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

async function mountTool(): Promise<void> {
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(QrBarcodeTool).use(i18n)
  app.mount(host)
  await nextTick()
}

async function typeData(text: string): Promise<void> {
  const input = host.querySelector('input[maxlength="1000"]') as HTMLInputElement
  input.value = text
  input.dispatchEvent(new Event('input'))
  await nextTick()
  vi.advanceTimersByTime(500)
  await vi.runOnlyPendingTimersAsync()
  await nextTick()
}

const button = (label: string): HTMLButtonElement =>
  [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement

describe('QrBarcodeTool', () => {
  it('n’appelle pas le backend tant que le texte est vide', async () => {
    await mountTool()
    vi.advanceTimersByTime(1000)
    expect(calls).toEqual([])
    expect(host.textContent).toContain(enTool.noPreview)
  })

  it('affiche l’aperçu après un court délai de saisie', async () => {
    await mountTool()
    await typeData('hello')
    expect(calls.at(-1)).toMatchObject({
      action: 'generate',
      payload: { symbol: { kind: 'qr', data: 'hello' } },
    })
    const img = host.querySelector('img')
    expect(img?.getAttribute('src')).toContain('data:image/svg+xml')
    expect(img?.getAttribute('src')).toContain(encodeURIComponent('<svg></svg>'))
  })

  it('envoie le format choisi pour un code-barres', async () => {
    await mountTool()
    const radio = host.querySelector('input[value="barcode"]') as HTMLInputElement
    radio.click()
    await nextTick()
    const select = host.querySelector('select') as HTMLSelectElement
    select.value = 'ean13'
    select.dispatchEvent(new Event('change'))
    await nextTick()
    await typeData('590123412345')
    expect(calls.at(-1)?.payload).toMatchObject({
      symbol: { kind: 'barcode', data: '590123412345', barcode_type: 'ean13' },
    })
  })

  it('n’exporte rien si l’utilisateur annule le choix du dossier', async () => {
    await mountTool()
    await typeData('hello')
    button(enTool.export).click()
    await nextTick()
    await vi.runOnlyPendingTimersAsync()
    expect(calls.some((c) => c.action === 'export')).toBe(false)
  })

  it('exporte dans le dossier choisi et confirme le chemin', async () => {
    folderPick = 'C:/out'
    await mountTool()
    await typeData('hello')
    const name = host.querySelector('input[maxlength="60"]') as HTMLInputElement
    name.value = 'billet'
    name.dispatchEvent(new Event('input'))
    await nextTick()
    button(enTool.export).click()
    await vi.runOnlyPendingTimersAsync()
    await nextTick()
    expect(calls.at(-1)).toMatchObject({
      action: 'export',
      payload: { folder: 'C:/out', name: 'billet' },
    })
    expect(host.textContent).toContain('C:/out/billet.svg')
  })

  it('les textes FR et EN ont les mêmes clés', () => {
    setLanguage('fr')
    expect(Object.keys(frTool).sort()).toEqual(Object.keys(enTool).sort())
  })
})
