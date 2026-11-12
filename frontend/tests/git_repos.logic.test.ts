import { describe, expect, it } from 'vitest'
import {
  availableActions,
  filterRepos,
  needsAttention,
  relativeTime,
  sortRepos,
} from '../src/tools/git_repos/logic'
import type { RepoView } from '../src/tools/git_repos/types'
import enTool from '../src/tools/git_repos/i18n/en.json'
import frTool from '../src/tools/git_repos/i18n/fr.json'

const base = (o: Partial<RepoView> = {}): RepoView => ({
  path: 'p',
  root: 'r',
  name: 'n',
  rel_path: 'n',
  branch: 'main',
  detached: false,
  upstream: 'origin/main',
  ahead: 0,
  behind: 0,
  staged: 0,
  unstaged: 0,
  untracked: 0,
  conflicts: 0,
  operation: null,
  remote_url: 'u',
  host: 'github',
  last_fetch: null,
  changed_files: [],
  running: null,
  error: null,
  ...o,
})

describe('git_repos logic', () => {
  it('propre → pas à traiter', () => expect(needsAttention(base())).toBe(false))

  it.each([
    { unstaged: 1 },
    { staged: 1 },
    { untracked: 1 },
    { ahead: 1 },
    { behind: 1 },
    { conflicts: 1 },
    { operation: 'merge' as const },
    { upstream: null },
    { error: { code: 'timeout', message: 't' } },
  ])('à traiter : %o', (o) => expect(needsAttention(base(o))).toBe(true))

  it('pas de distant et pas de branche suivie → pas « non publiée »', () =>
    expect(needsAttention(base({ upstream: null, remote_url: null, host: 'none' }))).toBe(false))

  it('actions', () => {
    expect(availableActions(base({ behind: 2 }))).toEqual({ fetch: true, pull: true, push: false, commit: false })
    expect(availableActions(base({ upstream: null }))).toMatchObject({ push: true })
    expect(availableActions(base({ upstream: null, remote_url: null }))).toMatchObject({ push: false, fetch: false })
    expect(availableActions(base({ unstaged: 1 }))).toMatchObject({ commit: true })
    expect(availableActions(base({ unstaged: 1, conflicts: 1 }))).toMatchObject({ commit: false })
    expect(availableActions(base({ unstaged: 1, operation: 'rebase' }))).toMatchObject({ commit: false })
    expect(availableActions(base({ ahead: 1, detached: true }))).toMatchObject({ push: false })
    expect(availableActions(base({ behind: 1, operation: 'merge' }))).toMatchObject({ pull: false })
    expect(availableActions(base({ running: 'fetch', behind: 1 }))).toEqual({
      fetch: false,
      pull: false,
      push: false,
      commit: false,
    })
  })

  it('tri : à traiter d’abord puis par nom', () =>
    expect(sortRepos([base({ name: 'b' }), base({ name: 'c', ahead: 1 }), base({ name: 'a' })]).map((r) => r.name)).toEqual([
      'c',
      'a',
      'b',
    ]))

  it('filtre et recherche (sans accents ni casse)', () => {
    const rs = [base({ name: 'Été', rel_path: 'x/Été' }), base({ name: 'zzz', ahead: 1 })]
    expect(filterRepos(rs, 'ete', false).map((r) => r.name)).toEqual(['Été'])
    expect(filterRepos(rs, 'X/', false).map((r) => r.name)).toEqual(['Été'])
    expect(filterRepos(rs, '', true).map((r) => r.name)).toEqual(['zzz'])
    expect(filterRepos(rs, '  ', false)).toHaveLength(2)
  })

  it('temps relatif', () => {
    const t = (k: string, p?: object) => `${k}:${(p as { n?: number } | undefined)?.n ?? ''}`
    const now = new Date('2026-11-12T12:00:00Z')
    expect(relativeTime(null, now, t)).toBe('relative.never:')
    expect(relativeTime('2026-11-12T11:59:30Z', now, t)).toBe('relative.now:')
    expect(relativeTime('2026-11-12T11:48:00Z', now, t)).toBe('relative.minutes:12')
    expect(relativeTime('2026-11-12T09:00:00Z', now, t)).toBe('relative.hours:3')
    expect(relativeTime('2026-11-10T12:00:00Z', now, t)).toBe('relative.days:2')
  })
})

function flatKeys(o: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    v !== null && typeof v === 'object' ? flatKeys(v as Record<string, unknown>, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

describe('git_repos i18n', () => {
  it('fr et en ont les mêmes clés', () => expect(flatKeys(frTool).sort()).toEqual(flatKeys(enTool).sort()))

  it('traduit les 13 codes d’erreur', () => {
    const codes = [
      'not_a_repo',
      'diverged',
      'nothing_to_commit',
      'empty_message',
      'detached_head',
      'in_progress',
      'no_remote',
      'auth_required',
      'timeout',
      'git_failed',
      'unknown_repo',
      'git_not_found',
      'busy',
    ]
    for (const c of codes) expect(flatKeys(frTool)).toContain(`errors.${c}`)
  })
})
