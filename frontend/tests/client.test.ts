import { afterEach, describe, expect, it } from 'vitest'
import { BridgeError, getBootstrap, saveSettings, setAutostart, toolCall, waitForBridge } from '../src/bridge/client'

type Api = Record<string, (...args: unknown[]) => Promise<unknown>>

function mockApi(api: Api) {
  ;(window as unknown as { pywebview?: { api: Api } }).pywebview = { api }
}

afterEach(() => {
  delete (window as unknown as { pywebview?: unknown }).pywebview
})

describe('bridge client', () => {
  it('déballe ok:true', async () => {
    mockApi({ tool_call: async () => ({ ok: true, data: 42 }) })
    expect(await toolCall<number>('t', 'a')).toBe(42)
  })

  it('lève BridgeError sur ok:false', async () => {
    mockApi({ tool_call: async () => ({ ok: false, error: { code: 'unknown_tool', message: 'x' } }) })
    await expect(toolCall('t', 'a')).rejects.toMatchObject({ code: 'unknown_tool' })
    await expect(toolCall('t', 'a')).rejects.toBeInstanceOf(BridgeError)
  })

  it('transmet les arguments à tool_call', async () => {
    const seen: unknown[][] = []
    mockApi({ tool_call: async (...args) => (seen.push(args), { ok: true, data: null }) })
    await toolCall('t', 'a', { x: 1 })
    expect(seen[0]).toEqual(['t', 'a', { x: 1 }])
  })

  it('getBootstrap, saveSettings et setAutostart déballent', async () => {
    mockApi({
      get_bootstrap: async () => ({ ok: true, data: { warnings: [] } }),
      save_settings: async (s) => ({ ok: true, data: s }),
      set_autostart: async (e) => ({ ok: true, data: { available: true, enabled: e } }),
    })
    expect(await getBootstrap()).toEqual({ warnings: [] })
    expect(await saveSettings({ language: 'fr' } as never)).toEqual({ language: 'fr' })
    expect(await setAutostart(true)).toEqual({ available: true, enabled: true })
  })

  it('waitForBridge résout immédiatement si le pont existe', async () => {
    mockApi({ get_bootstrap: async () => ({ ok: true, data: {} }) })
    await expect(waitForBridge()).resolves.toBeUndefined()
  })

  it("waitForBridge attend pywebviewready si l'api est encore vide", async () => {
    mockApi({})
    let done = false
    const p = waitForBridge().then(() => {
      done = true
    })
    await Promise.resolve()
    expect(done).toBe(false)
    window.dispatchEvent(new Event('pywebviewready'))
    await p
    expect(done).toBe(true)
  })

  it("waitForBridge attend l'évènement pywebviewready", async () => {
    let done = false
    const p = waitForBridge().then(() => {
      done = true
    })
    await Promise.resolve()
    expect(done).toBe(false)
    window.dispatchEvent(new Event('pywebviewready'))
    await p
    expect(done).toBe(true)
  })
})
