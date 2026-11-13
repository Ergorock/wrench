// Mirrors of the Pydantic models in backend/src/wrench/tools/projects/scan.py and service.py.
import type { RepoView } from '../git_repos/types'

export interface ProjectEntry {
  name: string
  path: string
  rel_path: string
  techs: string[]
  is_template: boolean
}

export interface FolderEntry {
  name: string
  path: string
  rel_path: string
  project_count: number
  folders: FolderEntry[]
  projects: ProjectEntry[]
}

export interface Config {
  root: string | null
  templates_dir: string | null
  max_depth: number
  root_missing: boolean
  templates_missing: boolean
}

/** The git state of a project; `running` is a free operation name (status, commit, push…). */
export type GitView = Omit<RepoView, 'running'> & { running: string | null }

export interface CreationView {
  running: boolean
  error: { code: string; message: string } | null
  created: string | null
}

export interface State {
  scanning: boolean
  scan_error: { code: string; message: string } | null
  git_available: boolean
  tree: FolderEntry | null
  git: Record<string, GitView>
  creation: CreationView | null
}

export interface BuildInfo {
  command: string | null
  suggested: string | null
}

export interface EditorView {
  id: string
  name: string
  exe: string
  available: boolean
}

export type RequirementStatus = 'ok' | 'too_old' | 'missing' | 'unknown' | 'manual'

export interface Requirement {
  tool: string
  required: string | null
  installed: string | null
  status: RequirementStatus
  source: string
}

export interface RequirementsView {
  running: boolean
  items: Requirement[] | null
  error: { code: string; message: string } | null
}
