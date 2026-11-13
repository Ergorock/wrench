import type { LocalBranch, RepoView } from './types'

type Translate = (k: string, p?: object, n?: number) => string

export interface RepoActions {
  fetch: boolean
  pull: boolean
  push: boolean
  commit: boolean
}

export function changeCount(r: RepoView): number {
  return r.staged + r.unstaged + r.untracked
}

/** A branch with a remote but no tracked branch: it has never been pushed. */
export function isUnpublished(r: RepoView): boolean {
  return r.branch !== null && r.upstream === null && r.remote_url !== null
}

export function needsAttention(r: RepoView): boolean {
  return (
    changeCount(r) > 0 ||
    r.ahead > 0 ||
    r.behind > 0 ||
    r.conflicts > 0 ||
    r.operation !== null ||
    isUnpublished(r) ||
    r.error !== null
  )
}

export function availableActions(r: RepoView): RepoActions {
  if (r.running !== null) return { fetch: false, pull: false, push: false, commit: false }
  const onBranch = !r.detached && r.operation === null
  const hasRemote = r.remote_url !== null
  return {
    fetch: hasRemote,
    pull: r.behind > 0 && onBranch,
    push: (r.ahead > 0 || isUnpublished(r)) && hasRemote && onBranch,
    commit: changeCount(r) > 0 && r.conflicts === 0 && onBranch,
  }
}

const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true })

/** Repositories needing attention first, then by name. */
export function sortRepos(rs: RepoView[]): RepoView[] {
  return [...rs].sort(
    (a, b) => Number(needsAttention(b)) - Number(needsAttention(a)) || collator.compare(a.name, b.name),
  )
}

function fold(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
}

/** Search on the name and relative path, ignoring case and accents. */
export function filterRepos(rs: RepoView[], query: string, onlyAttention: boolean): RepoView[] {
  const q = fold(query.trim())
  return rs.filter(
    (r) =>
      (!onlyAttention || needsAttention(r)) &&
      (q === '' || fold(r.name).includes(q) || fold(r.rel_path).includes(q)),
  )
}

export function relativeTime(
  iso: string | null,
  now: Date,
  t: (k: string, p?: object) => string,
): string {
  if (iso === null) return t('relative.never')
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return t('relative.now')
  if (minutes < 60) return t('relative.minutes', { n: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('relative.hours', { n: hours })
  return t('relative.days', { n: Math.floor(hours / 24) })
}

/** Tooltip of the host icon: kind of hosting, then the web address when known. */
export function hostTitle(r: RepoView, t: Translate): string {
  const label = t(`badges.hostTitle.${r.host}`)
  if (r.web_url === null) return label
  return t('badges.hostTitleUrl', { label, url: r.web_url.replace(/^https?:\/\//, '') })
}

export function branchTitle(r: RepoView, t: Translate): string {
  if (r.detached || r.branch === null) return t('badges.branchTitle.detached')
  if (r.upstream === null) return t('badges.branchTitle.untracked', { branch: r.branch })
  return t('badges.branchTitle.tracking', { branch: r.branch, upstream: r.upstream })
}

/** « ✓ merged » or « +N commits » against the main branch; empty without a main branch. */
export function mergeLabel(b: LocalBranch, t: Translate): string {
  if (b.merged === null || b.commits_not_in_main === null) return ''
  if (b.merged) return t('branches.merged')
  return t('branches.notInMain', { n: b.commits_not_in_main }, b.commits_not_in_main)
}
