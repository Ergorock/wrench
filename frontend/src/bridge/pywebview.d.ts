import type { Envelope } from './types'

declare global {
  interface Window {
    pywebview?: {
      api: {
        get_bootstrap(): Promise<Envelope<unknown>>
        save_settings(settings: unknown): Promise<Envelope<unknown>>
        set_autostart(enabled: boolean): Promise<Envelope<unknown>>
        get_update_status(): Promise<Envelope<unknown>>
        check_for_updates(): Promise<Envelope<unknown>>
        install_update(): Promise<Envelope<unknown>>
        open_url(url: string): Promise<Envelope<unknown>>
        tool_call(toolId: string, action: string, payload?: object | null): Promise<Envelope<unknown>>
      }
    }
  }
}

export {}
