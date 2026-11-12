export type Language = 'fr' | 'en'
export type ThemePref = 'light' | 'dark' | 'system'

export interface SidebarSettings {
  collapsed: boolean
  category_order: string[]
  tool_order: Record<string, string[]>
  favorites: string[]
}

export interface ToolSettings {
  enabled: boolean
}

export interface WindowSettings {
  x: number | null
  y: number | null
  width: number
  height: number
  maximized: boolean
}

export interface Settings {
  schema_version: 1
  language: Language
  theme: ThemePref
  autostart: boolean
  sidebar: SidebarSettings
  tools: Record<string, ToolSettings>
  window: WindowSettings
  last_tool: string | null
}

export interface ToolManifest {
  id: string
  category: string
  icon: string
  version: string
  enabled_by_default: boolean
}

export interface Category {
  id: string
  icon: string
}

export interface AutostartState {
  available: boolean
  enabled: boolean
}

export interface Bootstrap {
  settings: Settings
  categories: Category[]
  tools: ToolManifest[]
  autostart: AutostartState
  warnings: string[]
}

export type Envelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } }
