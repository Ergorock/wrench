import { describe, expect, it } from 'vitest'
import { matches, normalize } from '../src/tools/quick_reference/filter'

describe('quick_reference filter', () => {
  it('normalise accents, casse et espaces', () => {
    expect(normalize('  Écran  DE ')).toBe('ecran de')
  })

  it('une requête vide correspond à tout', () => {
    expect(matches('Historique', 'git log', '')).toBe(true)
    expect(matches('Historique', 'git log', '   ')).toBe(true)
  })

  it('chaque mot doit apparaître dans la description ou la commande', () => {
    expect(matches('Mettre de côté', 'git stash push', 'stash mettre')).toBe(true)
    expect(matches('Mettre de côté', 'git stash push', 'stash rebase')).toBe(false)
  })
})
