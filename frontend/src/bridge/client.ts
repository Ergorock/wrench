import type { AutostartState, Bootstrap, Envelope, Settings } from './types'

export class BridgeError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'BridgeError'
    this.code = code
  }
}

export function waitForBridge(): Promise<void> {
  if (window.pywebview?.api) return Promise.resolve()
  return new Promise((resolve) => {
    window.addEventListener('pywebviewready', () => resolve(), { once: true })
  })
}

async function unwrap<T>(pending: Promise<Envelope<unknown>>): Promise<T> {
  const res = await pending
  if (!res.ok) throw new BridgeError(res.error.code, res.error.message)
  return res.data as T
}

function api() {
  const a = window.pywebview?.api
  if (!a) throw new BridgeError('internal_error', 'pywebview bridge unavailable')
  return a
}

export const getBootstrap = (): Promise<Bootstrap> => unwrap(api().get_bootstrap())

export const saveSettings = (s: Settings): Promise<Settings> => unwrap(api().save_settings(s))

export const setAutostart = (enabled: boolean): Promise<AutostartState> =>
  unwrap(api().set_autostart(enabled))

export function toolCall<T>(toolId: string, action: string, payload?: object): Promise<T> {
  return unwrap(api().tool_call(toolId, action, payload))
}
