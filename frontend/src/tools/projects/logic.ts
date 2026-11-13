import type { FolderEntry, GitView, ProjectEntry } from './types'

export type Badge = { kind: 'changes' | 'ahead' | 'conflict' | 'clean'; n?: number }

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

function allProjects(folder: FolderEntry): ProjectEntry[] {
  return [...folder.projects, ...folder.folders.flatMap(allProjects)]
}

/** Projects of the whole inventory whose name contains the query, by name. */
export function searchProjects(tree: FolderEntry, query: string): ProjectEntry[] {
  const q = normalize(query.trim())
  return byName(allProjects(tree).filter((p) => normalize(p.name).includes(q)))
}

export const needsTemplateConfirm = (p: ProjectEntry): boolean => p.is_template

export function gitBadges(g: GitView | undefined): Badge[] {
  // Nothing is known until the first read has ended.
  if (!g || g.running !== null) return []
  const badges: Badge[] = []
  if (g.conflicts > 0) badges.push({ kind: 'conflict' })
  const changes = g.staged + g.unstaged + g.untracked
  if (changes > 0) badges.push({ kind: 'changes', n: changes })
  if (g.ahead > 0) badges.push({ kind: 'ahead', n: g.ahead })
  return badges.length > 0 ? badges : [{ kind: 'clean' }]
}
