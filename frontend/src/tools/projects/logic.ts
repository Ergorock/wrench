import type { BuildInfo, FolderEntry, GitView, ProjectEntry, RequirementStatus } from './types'

export type Badge = { kind: 'changes' | 'ahead' | 'conflict' | 'clean' | 'error'; n?: number }

/** Lowercase, without accents. */
export function normalize(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

export const byName = <T extends { name: string }>(items: T[]): T[] =>
  [...items].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))

const SEP = '\\'

export function findFolder(tree: FolderEntry, relPath: string): FolderEntry | null {
  let current = tree
  for (const part of relPath ? relPath.split(SEP) : []) {
    const next = current.folders.find((f) => f.name === part)
    if (!next) return null
    current = next
  }
  return current
}

export function breadcrumb(tree: FolderEntry, relPath: string): { name: string; relPath: string }[] {
  const crumbs = [{ name: tree.name, relPath: '' }]
  const parts = relPath ? relPath.split(SEP) : []
  parts.forEach((name, i) => crumbs.push({ name, relPath: parts.slice(0, i + 1).join(SEP) }))
  return crumbs
}

export type ViewMode = 'cards' | 'list' | 'tree'
export const VIEW_MODES: ViewMode[] = ['cards', 'list', 'tree']

/** The stored view mode, cards when absent or unknown. */
export const parseViewMode = (raw: string | null): ViewMode => VIEW_MODES.find((m) => m === raw) ?? 'cards'

export type TreeRow =
  | { kind: 'folder'; folder: FolderEntry; depth: number; expanded: boolean }
  | { kind: 'project'; project: ProjectEntry; depth: number }

/** The rows of the tree view: every folder then every project, depth-first, children of expanded folders only. */
export function treeRows(folder: FolderEntry, expanded: ReadonlySet<string>, depth = 0): TreeRow[] {
  const rows: TreeRow[] = []
  for (const f of byName(folder.folders)) {
    const open = expanded.has(f.rel_path)
    rows.push({ kind: 'folder', folder: f, depth, expanded: open })
    if (open) rows.push(...treeRows(f, expanded, depth + 1))
  }
  for (const p of byName(folder.projects)) rows.push({ kind: 'project', project: p, depth })
  return rows
}

/** Every folder of the inventory, the root first then the others in tree order, by relative path. */
export function folderOptions(tree: FolderEntry): { label: string; relPath: string }[] {
  const walk = (f: FolderEntry): FolderEntry[] => byName(f.folders).flatMap((c) => [c, ...walk(c)])
  return [{ label: tree.name, relPath: '' }, ...walk(tree).map((f) => ({ label: f.rel_path, relPath: f.rel_path }))]
}

function allProjects(folder: FolderEntry): ProjectEntry[] {
  return [...folder.projects, ...folder.folders.flatMap(allProjects)]
}

/** Projects of the whole inventory whose name contains the query, by name. */
export function searchProjects(tree: FolderEntry, query: string): ProjectEntry[] {
  const q = normalize(query.trim())
  return byName(allProjects(tree).filter((p) => normalize(p.name).includes(q)))
}

/** The project at `path` anywhere in the inventory; null once it has vanished. */
export const findProject = (tree: FolderEntry, path: string): ProjectEntry | null =>
  allProjects(tree).find((p) => p.path === path) ?? null

/** True when the build field holds something other than the saved command (saved on blur or Enter). */
export const buildDraftChanged = (info: BuildInfo, draft: string): boolean => draft.trim() !== (info.command ?? '')

export const needsTemplateConfirm = (p: ProjectEntry): boolean => p.is_template

export function gitBadges(g: GitView | undefined): Badge[] {
  // Nothing is known until the first read has ended; a push or a commit keeps the last known state.
  if (!g || g.running === 'status') return []
  const badges: Badge[] = []
  if (g.conflicts > 0) badges.push({ kind: 'conflict' })
  const changes = g.staged + g.unstaged + g.untracked
  if (changes > 0) badges.push({ kind: 'changes', n: changes })
  if (g.ahead > 0) badges.push({ kind: 'ahead', n: g.ahead })
  // A failed read is never shown as clean.
  if (g.error) badges.push({ kind: 'error' })
  return badges.length > 0 ? badges : [{ kind: 'clean' }]
}

const REQUIREMENT_ICONS: Record<RequirementStatus, string> = {
  ok: 'check',
  too_old: 'alert',
  missing: 'x',
  unknown: 'help',
  manual: 'hand',
}
/** Name of the icon of a requirement status (the panel maps it to a component). */
export const requirementIcon = (s: RequirementStatus): string => REQUIREMENT_ICONS[s]
export const requirementLabelKey = (s: RequirementStatus): string => `tools.projects.requirements.status.${s}`

// Same rule as is_remote_url in the backend (wrench/shared/git/remote.py).
const SCP = /^(?:([^@/\\\s]+)@)?([^@/\\:\s]{2,}):(?!\/\/)(.+)$/
const trimSlashes = (s: string): string => s.replace(/^\/+|\/+$/g, '')
/** `https://host/path`, `ssh://[user@]host[:port]/path` or `user@host:path`. */
export function isRemoteUrl(url: string): boolean {
  if (!url || url.startsWith('-') || /[\s\x00-\x1f\x7f]/.test(url)) return false
  if (!url.includes('://')) {
    const m = SCP.exec(url)
    return !!m && !!m[1] && trimSlashes(m[3]) !== ''
  }
  try {
    const u = new URL(url)
    const scheme = u.protocol.slice(0, -1)
    return (scheme === 'https' || scheme === 'ssh') && u.hostname !== '' && trimSlashes(u.pathname) !== ''
  } catch {
    return false
  }
}
