export type Target = 'eda' | 'mashup' | 'xtend' | 'workspaces'

export interface Config {
  tenant: string
  eda_base_url: string
  company: string
  division: string
  language: string
  output_dir: string
}

export interface JobView {
  kind: string | null
  running: boolean
  status: string
  done: number
  total: number
  ok: number
  failed: number
  log: string[]
  error: { code: string; message: string } | null
  seq: number
}

export interface State {
  config: Config
  connected: Record<Target, boolean>
  job: JobView
}

export interface Mashup {
  name: string
  description: string
  category: number
  visibility: number
  created_by: string
  changed_by: string
  change_date: string
}

export interface Workspace {
  id: string
  title: string
  owner: string
  changed: string
}

export interface WidgetTotal {
  widget_id: string
  label: string
  count: number
}

export interface WidgetRow extends WidgetTotal {
  workspace_title: string
  workspace_id: string
}

export interface WsResult {
  totals: WidgetTotal[]
  rows: WidgetRow[]
}

export interface XtendSource {
  uuid: string
  program: string
  kind: 'batch' | 'transaction'
  name: string
  description: string
  modified: number
  modified_by: string
}

export interface XtendHit {
  file: string
  program: string
  kind: 'batch' | 'transaction'
  name: string
  line: number
  snippet: string
}

export interface EdaItem {
  id: string
  fields: Record<string, string>
}
