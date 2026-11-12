import type { Envelope } from './types'

declare global {
  interface Window {
    pywebview?: {
      api: {
        get_bootstrap(): Promise<Envelope<unknown>>
        save_settings(settings: unknown): Promise<Envelope<unknown>>
        set_autostart(enabled: boolean): Promise<Envelope<unknown>>
        tool_call(toolId: string, action: string, payload?: object | null): Promise<Envelope<unknown>>
      }
    }
  }
}

export {}
