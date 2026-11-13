// Mirrors of the Pydantic models in backend/src/wrench/tools/window_layout/service.py.
export interface OpenItem {
  exe: string
  title: string
}

export interface OpenWindows {
  windows: OpenItem[]
}

export interface Layout {
  id: string
  name: string
  saved_at: string
  windows: { exe: string; title: string }[]
}

export interface Layouts {
  layouts: Layout[]
}

export interface Restore {
  restored: number
  missing: OpenItem[]
}
