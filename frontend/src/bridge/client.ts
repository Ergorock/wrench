import type { AutostartState, Bootstrap, Envelope, Settings, UpdateStatus } from './types'

export class BridgeError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'BridgeError'
    this.code = code
  }
}

export function waitForBridge(): Promise<void> {
  // pywebview injects `api: {}` first and fills it just before firing pywebviewready.
  if (typeof window.pywebview?.api?.get_bootstrap === 'function') return Promise.resolve()
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

export const getUpdateStatus = (): Promise<UpdateStatus> => unwrap(api().get_update_status())

export const checkForUpdates = (): Promise<UpdateStatus> => unwrap(api().check_for_updates())

export const installUpdate = (): Promise<UpdateStatus> => unwrap(api().install_update())

export const openUrl = (url: string): Promise<null> => unwrap(api().open_url(url))
