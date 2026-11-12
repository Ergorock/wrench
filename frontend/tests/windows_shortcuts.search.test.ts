/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { BridgeError } from '../src/bridge/client'
import { setLanguage } from '../src/i18n'
import { errorMessage } from '../src/shell/toasts'
import fr from '../src/tools/windows_shortcuts/i18n/fr.json'
import en from '../src/tools/windows_shortcuts/i18n/en.json'
import { matches, normalize } from '../src/tools/windows_shortcuts/search'
import type { Catalog } from '../src/tools/windows_shortcuts/types'

// vitest runs from frontend/ (npm test): the backend catalog is one level up.
const catalogPath = resolve(
  process.cwd(),
  '../backend/src/wrench/tools/windows_shortcuts/data/shortcuts.json',
)
const catalogRaw = readFileSync(catalogPath, 'utf-8')

const e = (description: string, keyLabels: string[], keyIds = keyLabels) => ({
  id: 'x',
  description,
  keyLabels,
  keyIds,
})

describe('normalize', () => {
  it('retire accents, casse et espaces superflus', () => {
    expect(normalize('  Écran   DE  Capture ')).toBe('ecran de capture')
  })
})

describe('matches', () => {
  it('requête vide ou espaces → tout', () => {
    expect(matches(e('a', []), '')).toBe(true)
    expect(matches(e('a', []), '   ')).toBe(true)
  })

  it('ignore accents et casse', () => {
    expect(matches(e("Capture d'écran", ['Win']), 'ECRAN')).toBe(true)
    expect(matches(e('Écran', ['Win']), 'capture')).toBe(false)
    expect(matches(e('capture', ['Win']), 'CAPTURE')).toBe(true)
  })

  it('tous les mots requis', () => {
    expect(matches(e('Ancrer à gauche', ['Win', '←'], ['Win', 'Left']), 'win gauche')).toBe(true)
    expect(matches(e('Ancrer à gauche', ['Win', '←'], ['Win', 'Left']), 'win droite')).toBe(false)
  })

  it("trouve via l'id de touche brut en FR", () => {
    expect(matches(e('Capture', ['Win', 'Maj', 'S'], ['Win', 'Shift', 'S']), 'win shift')).toBe(true)
  })
})

type Messages = {
  name: string
  description: string
  searchPlaceholder: string
  favorites: string
  noResults: string
  pin: string
  unpin: string
  groups: Record<string, string>
  shortcuts: Record<string, string>
  keys: Record<string, string>
  errors: Record<string, string>
}

const catalog = JSON.parse(catalogRaw) as Omit<Catalog, 'favorites'>
const ids = catalog.groups.flatMap((g) => g.shortcuts.map((s) => s.id))
const keyIds = new Set(catalog.groups.flatMap((g) => g.shortcuts.flatMap((s) => s.keys)))
const needsLabel = [...keyIds].filter((k) => !/^([A-Z0-9]|F([1-9]|1[0-2]))$/.test(k))

describe.each([
  ['fr', fr as Messages],
  ['en', en as Messages],
])('traductions %s de windows_shortcuts', (_lang, m) => {
  it('chaque raccourci du JSON backend a un libellé, et inversement', () => {
    expect(Object.keys(m.shortcuts).sort()).toEqual([...ids].sort())
  })

  it('chaque groupe du JSON backend a un libellé, et inversement', () => {
    expect(Object.keys(m.groups).sort()).toEqual(catalog.groups.map((g) => g.id).sort())
  })

  it('les touches non alphanumériques sont traduites, les lettres, chiffres et F1-F12 non', () => {
    expect(Object.keys(m.keys).sort()).toEqual([...needsLabel].sort())
  })

  it('contient les clés de base', () => {
    for (const k of ['name', 'description', 'searchPlaceholder', 'favorites', 'noResults', 'pin', 'unpin'] as const) {
      expect(m[k], k).toBeTruthy()
    }
  })
})

describe('traductions fr / en', () => {
  it('ont exactement les mêmes clés', () => {
    const flat = (o: object, p = ''): string[] =>
      Object.entries(o).flatMap(([k, v]) =>
        v !== null && typeof v === 'object' ? flat(v, `${p}${k}.`) : [`${p}${k}`],
      )
    expect(flat(fr).sort()).toEqual(flat(en).sort())
  })

  it('traduit Shift, Del, Esc, Enter, Space, PrtSc et les flèches comme prévu', () => {
    expect(fr.keys).toMatchObject({
      Shift: 'Maj',
      Del: 'Suppr',
      Esc: 'Échap',
      Enter: 'Entrée',
      Space: 'Espace',
      PrtSc: 'Impr. écran',
      Left: '←',
      Right: '→',
      Up: '↑',
      Down: '↓',
    })
    expect(en.keys).toMatchObject({ Left: '←', Right: '→', Up: '↑', Down: '↓' })
  })
})

describe('erreurs propres à windows_shortcuts', () => {
  afterEach(() => setLanguage('en'))

  it('errorMessage renvoie le texte de errors.unknown_shortcut, en fr puis en en', () => {
    const err = new BridgeError('unknown_shortcut', 'x')
    setLanguage('fr')
    expect(errorMessage(err, 'windows_shortcuts')).toBe(fr.errors.unknown_shortcut)
    setLanguage('en')
    expect(errorMessage(err, 'windows_shortcuts')).toBe(en.errors.unknown_shortcut)
    expect(fr.errors.unknown_shortcut).not.toBe(en.errors.unknown_shortcut)
  })
})
