import { describe, expect, it } from 'vitest'
import fr from '../src/i18n/fr.json'
import en from '../src/i18n/en.json'
import { i18n, setLanguage } from '../src/i18n'

function flatKeys(o: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    v !== null && typeof v === 'object'
      ? flatKeys(v as Record<string, unknown>, `${prefix}${k}.`)
      : [`${prefix}${k}`],
  )
}

describe('i18n', () => {
  it('fr et en de la coquille ont les mêmes clés', () => {
    expect(flatKeys(fr).sort()).toEqual(flatKeys(en).sort())
  })

  it('couvre les codes d’erreur du pont', () => {
    const keys = flatKeys(fr)
    for (const c of ['unknown_tool', 'unknown_action', 'invalid_payload', 'invalid_settings', 'autostart_unavailable', 'internal_error', 'generic']) {
      expect(keys).toContain(`errors.${c}`)
    }
  })

  it('le texte d’accueil ne dit pas « aucun outil installé » et invite à activer des outils', () => {
    expect(fr.home.body).not.toMatch(/install/i)
    expect(en.home.body).not.toMatch(/install/i)
    expect(fr.home.body).toMatch(/activ/i)
    expect(en.home.body).toMatch(/enable/i)
  })

  it('setLanguage change la locale et <html lang>', () => {
    setLanguage('fr')
    expect(i18n.global.locale.value).toBe('fr')
    expect(document.documentElement.lang).toBe('fr')
    setLanguage('en')
    expect(i18n.global.t('nav.settings')).toBe(en.nav.settings)
    expect(document.documentElement.lang).toBe('en')
  })
})
