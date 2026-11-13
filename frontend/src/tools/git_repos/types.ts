// Mirrors of the Pydantic models in backend/src/wrench/shared/git/status.py,
// backend/src/wrench/shared/git/history.py and backend/src/wrench/tools/git_repos/service.py.
export type HostKind = 'github' | 'gitea' | 'other' | 'none'
export type Operation = 'merge' | 'rebase' | 'cherry-pick' | 'revert'
export type RepoOp = 'fetch' | 'pull' | 'push' | 'commit'

export interface RepoError {
  code: string
  message: string
}

export interface RepoView {
  path: string
  root: string
  name: string
  rel_path: string
  web_url: string | null
  branch: string | null
  detached: boolean
  upstream: string | null
  ahead: number
  behind: number
  staged: number
  unstaged: number
  untracked: number
  conflicts: number
  operation: Operation | null
  remote_url: string | null
  host: HostKind
  last_fetch: string | null
  changed_files: string[]
  running: RepoOp | null
  error: RepoError | null
}

export interface RepoState {
  git_available: boolean
  repos: RepoView[]
}

export interface RepoConfig {
  roots: string[]
  max_depth: number
  missing_roots: string[]
}

export interface LocalBranch {
  name: string
  current: boolean
  upstream: string | null
  ahead: number
  behind: number
  /** Against the main branch; null for the main branch itself or without a main branch. */
  merged: boolean | null
  commits_not_in_main: number | null
  last_commit: string | null
}

export interface RemoteBranch {
  name: string
  last_commit: string | null
}

export interface BranchList {
  main: string | null
  local: LocalBranch[]
  remote: RemoteBranch[]
}

export interface CommitInfo {
  short_hash: string
  hash: string
  subject: string
  message: string
  author: string
  date: string
  unpushed: boolean
}
