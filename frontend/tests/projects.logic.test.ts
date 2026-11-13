import { describe, expect, it } from 'vitest'
import {
  breadcrumb,
  buildDraftChanged,
  findFolder,
  findProject,
  folderOptions,
  gitBadges,
  isRemoteUrl,
  needsTemplateConfirm,
  normalize,
  requirementIcon,
  requirementLabelKey,
  searchProjects,
} from '../src/tools/projects/logic'
import type { FolderEntry, GitView, ProjectEntry } from '../src/tools/projects/types'
import enTool from '../src/tools/projects/i18n/en.json'
import frTool from '../src/tools/projects/i18n/fr.json'

const project = (name: string, rel: string, o: Partial<ProjectEntry> = {}): ProjectEntry => ({
  name,
  path: `C:\\Dev\\${rel}`,
  rel_path: rel,
  techs: [],
  is_template: false,
  exe: null,
  ...o,
})
const folder = (name: string, rel: string, folders: FolderEntry[], projects: ProjectEntry[]): FolderEntry => ({
  name,
  path: `C:\\Dev\\${rel}`,
  rel_path: rel,
  project_count: projects.length,
  folders,
  projects,
})

const tree = folder('Dev', '', [
  folder('M3', 'M3', [folder('Liste', 'M3\\Liste', [], [project('Génération aspx', 'M3\\Liste\\Génération aspx')])], [
    project('zeta', 'M3\\zeta'),
  ]),
], [project('Alpha', 'Alpha')])

const git = (o: Partial<GitView> = {}): GitView =>
  ({ staged: 0, unstaged: 0, untracked: 0, ahead: 0, conflicts: 0, running: null, ...o }) as GitView

describe('projects logic', () => {
  it('normalize ignore la casse et les accents', () => {
    expect(normalize('Génération ÀÉ')).toBe('generation ae')
  })

  it('searchProjects trouve « Génération aspx » avec « generation », triés par nom', () => {
    expect(searchProjects(tree, 'generation').map((p) => p.name)).toEqual(['Génération aspx'])
    expect(searchProjects(tree, 'A').map((p) => p.name)).toEqual(['Alpha', 'Génération aspx', 'zeta'])
  })

  it('findFolder : racine, sous-dossier, chemin inexistant', () => {
    expect(findFolder(tree, '')?.name).toBe('Dev')
    expect(findFolder(tree, 'M3\\Liste')?.name).toBe('Liste')
    expect(findFolder(tree, 'M3\\Nope')).toBeNull()
  })

  it('breadcrumb de M3\\Liste donne racine, M3, Liste', () => {
    expect(breadcrumb(tree, 'M3\\Liste')).toEqual([
      { name: 'Dev', relPath: '' },
      { name: 'M3', relPath: 'M3' },
      { name: 'Liste', relPath: 'M3\\Liste' },
    ])
    expect(breadcrumb(tree, '')).toEqual([{ name: 'Dev', relPath: '' }])
  })

  it('needsTemplateConfirm suit is_template', () => {
    expect(needsTemplateConfirm(project('t', 't', { is_template: true }))).toBe(true)
    expect(needsTemplateConfirm(project('p', 'p'))).toBe(false)
  })

  it('gitBadges : conflit, modifications, commits à pousser, propre', () => {
    expect(gitBadges(undefined)).toEqual([])
    expect(gitBadges(git({ running: 'status' }))).toEqual([])
    expect(gitBadges(git())).toEqual([{ kind: 'clean' }])
    expect(gitBadges(git({ conflicts: 1, staged: 1, unstaged: 1, untracked: 1, ahead: 2 }))).toEqual([
      { kind: 'conflict' },
      { kind: 'changes', n: 3 },
      { kind: 'ahead', n: 2 },
    ])
  })

  it('gitBadges : erreur sans badge propre ; push en cours garde les badges connus', () => {
    const err = { code: 'git_failed', message: 'boom' }
    expect(gitBadges(git({ error: err }))).toEqual([{ kind: 'error' }])
    expect(gitBadges(git({ running: 'push', unstaged: 2 }))).toEqual([{ kind: 'changes', n: 2 }])
    expect(gitBadges(git({ running: 'commit' }))).toEqual([{ kind: 'clean' }])
  })

  it('fr.json et en.json ont les mêmes clés', () => {
    const keys = (o: object, p = ''): string[] =>
      Object.entries(o).flatMap(([k, v]) => (typeof v === 'object' ? keys(v, `${p}${k}.`) : [`${p}${k}`]))
    expect(keys(frTool).sort()).toEqual(keys(enTool).sort())
  })
})

describe('projects logic, fiche', () => {
  const tree = folder('Dev', '', [folder('M3', 'M3', [], [project('Deep', 'M3\\Deep')])], [project('Alpha', 'Alpha')])

  it('findProject cherche dans tout l’inventaire, null si le projet a disparu', () => {
    expect(findProject(tree, 'C:\\Dev\\M3\\Deep')?.name).toBe('Deep')
    expect(findProject(tree, 'C:\\Dev\\Alpha')?.name).toBe('Alpha')
    expect(findProject(tree, 'C:\\Dev\\Gone')).toBeNull()
  })

  it('buildDraftChanged : le champ Build ne s’enregistre que s’il diffère de la commande enregistrée', () => {
    expect(buildDraftChanged({ command: 'npm run build', suggested: null }, 'npm run build')).toBe(false)
    expect(buildDraftChanged({ command: 'npm run build', suggested: null }, ' npm run build ')).toBe(false)
    expect(buildDraftChanged({ command: null, suggested: 'npm run build' }, '')).toBe(false)
    expect(buildDraftChanged({ command: null, suggested: 'npm run build' }, 'make')).toBe(true)
    expect(buildDraftChanged({ command: 'make', suggested: null }, '')).toBe(true)
  })
})

describe('requirements', () => {
  const statuses = ['ok', 'too_old', 'missing', 'unknown', 'manual'] as const

  it('chaque état a une icône distincte', () => {
    const icons = statuses.map(requirementIcon)
    expect(new Set(icons).size).toBe(statuses.length)
  })

  it('chaque état a un libellé dans les deux langues', () => {
    for (const s of statuses) {
      expect(requirementLabelKey(s)).toBe(`tools.projects.requirements.status.${s}`)
      for (const json of [enTool, frTool]) expect(json.requirements.status[s]).toEqual(expect.any(String))
    }
  })
})

describe('isRemoteUrl', () => {
  it.each([
    'https://github.com/a/b.git',
    'ssh://git@host:2222/a/b',
    'git@github.com:a/b.git',
  ])('accepte %s', (u) => expect(isRemoteUrl(u)).toBe(true))

  it.each(['', 'ftp://x/y', 'https://host', 'https://host/', '-https://a/b', 'https://a/b c', 'C:/repos/x', 'host:path', 'https://h:99999/p'])(
    'refuse %j',
    (u) => expect(isRemoteUrl(u)).toBe(false),
  )
})

describe('projects errors i18n', () => {
  const codes = [
    'not_a_repo', 'no_build_command', 'empty_message', 'git_failed', 'check_failed', 'copy_failed',
    'editor_missing', 'launch_failed', 'invalid_name', 'target_exists', 'invalid_url', 'remote_exists',
    'not_a_project', 'busy', 'git_not_found', 'scan_failed', 'root_missing', 'templates_missing',
    'nothing_to_commit', 'no_remote', 'auth_required', 'timeout', 'detached_head', 'in_progress',
    'diverged', 'unknown_ref',
  ]
  it.each([
    ['fr', frTool],
    ['en', enTool],
  ])('chaque code d’erreur du backend est traduit (%s)', (_lang, tool) => {
    const errors = (tool as { errors: Record<string, string> }).errors
    expect(codes.filter((c) => !errors[c])).toEqual([])
  })
})

describe('folderOptions', () => {
  it('la racine d’abord, puis les dossiers triés dans l’ordre de l’arbre, accents conservés', () => {
    const t = folder('Dev', '', [
      folder('Zèbre', 'Zèbre', [], []),
      folder('M3', 'M3', [folder('Liste', 'M3\Liste', [], [])], []),
      folder('Éco', 'Éco', [], []),
    ], [])
    expect(folderOptions(t)).toEqual([
      { label: 'Dev', relPath: '' },
      { label: 'Éco', relPath: 'Éco' },
      { label: 'M3', relPath: 'M3' },
      { label: 'M3\Liste', relPath: 'M3\Liste' },
      { label: 'Zèbre', relPath: 'Zèbre' },
    ])
  })
})
