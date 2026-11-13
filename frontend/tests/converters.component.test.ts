import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import ConvertersTool from '../src/tools/converters/ConvertersTool.vue'
import enTool from '../src/tools/converters/i18n/en.json'

const units = {
  categories: [
    { id: 'length', units: ['mm', 'cm', 'm'] },
    { id: 'temperature', units: ['C', 'F', 'K'] },
  ],
}

let rates: { code: string; rate: number; date: string }[]
let calls: { action: string; payload?: Record<string, unknown> }[]
let app: App | null
let host: HTMLElement

// Fake backend: unit conversion is a simple ×100 for the test, currencies use the stored rates.
function fakeCall(action: string, payload?: Record<string, unknown>): unknown {
  calls.push({ action, payload })
  if (action === 'get_units') return units
  if (action === 'get_rates') return { base: 'EUR', rates }
  if (action === 'convert_unit') return (payload?.value as number) * 100
  if (action === 'convert_currency') return (payload?.value as number) * 2
  if (action === 'set_rate') {
    rates = [...rates, { code: payload?.code as string, rate: payload?.rate as number, date: payload?.day as string }]
    return { base: 'EUR', rates }
  }
  if (action === 'remove_rate') {
    rates = rates.filter((r) => r.code !== payload?.code)
    return { base: 'EUR', rates }
  }
  throw new Error(`unexpected ${action}`)
}

beforeEach(() => {
  rates = [{ code: 'USD', rate: 1.08, date: '2026-11-13' }]
  calls = []
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => ({
        ok: true,
        data: fakeCall(action, payload),
      }),
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
  app = createApp(ConvertersTool).use(i18n)
  app.mount(host)
  await flush()
}

const result = (id: string): string =>
  host.querySelector(`[data-testid="${id}"]`)?.textContent?.trim() ?? ''

const tabButton = (label: string): HTMLButtonElement =>
  [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement

describe('ConvertersTool', () => {
  it('convertit une valeur dans la grandeur choisie', async () => {
    await mountTool()
    expect(calls.map((c) => c.action)).toContain('get_units')
    expect(result('unit-result')).toContain('100')
    const convert = calls.filter((c) => c.action === 'convert_unit').at(-1)
    expect(convert?.payload).toEqual({ category: 'length', value: 1, source: 'mm', target: 'cm' })
  })

  it('une conversion de température ne rappelle pas le backend avec une unité de l’ancienne grandeur', async () => {
    await mountTool()
    const select = host.querySelector('select') as HTMLSelectElement
    select.value = 'temperature'
    select.dispatchEvent(new Event('change'))
    await flush()
    expect(toasts.value).toHaveLength(0)
    const last = calls.filter((c) => c.action === 'convert_unit').at(-1)
    expect(last?.payload).toMatchObject({ category: 'temperature', source: 'C', target: 'F' })
  })

  it('affiche les taux saisis et permet d’en ajouter un', async () => {
    setLanguage('en')
    await mountTool()
    tabButton(enTool.tabs.currencies).click()
    await flush()
    expect(host.querySelector('[data-rate="USD"]')?.textContent).toContain('1.08')

    const code = host.querySelector('input[placeholder="USD"]') as HTMLInputElement
    code.value = 'gbp'
    code.dispatchEvent(new Event('input'))
    const rate = host.querySelector('input[type="number"]') as HTMLInputElement
    rate.value = '0.87'
    rate.dispatchEvent(new Event('input'))
    host.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'))
    await flush()

    const setCall = calls.filter((c) => c.action === 'set_rate').at(-1)
    expect(setCall?.payload).toMatchObject({ code: 'GBP', rate: 0.87 })
    expect(host.querySelector('[data-rate="GBP"]')).not.toBeNull()
  })

  it('supprime un taux', async () => {
    await mountTool()
    tabButton(enTool.tabs.currencies).click()
    await flush()
    host.querySelector<HTMLButtonElement>('[data-rate="USD"] button')!.click()
    await flush()
    const removeCall = calls.filter((c) => c.action === 'remove_rate').at(-1)
    expect(removeCall).toEqual({ action: 'remove_rate', payload: { code: 'USD' } })
    expect(host.querySelector('[data-rate="USD"]')).toBeNull()
  })

  it('convertit des devises à partir des taux enregistrés', async () => {
    await mountTool()
    tabButton(enTool.tabs.currencies).click()
    await flush()
    const last = calls.filter((c) => c.action === 'convert_currency').at(-1)
    expect(last?.payload).toEqual({ value: 100, source: 'EUR', target: 'USD' })
    expect(result('money-result')).toContain('200')
  })
})
