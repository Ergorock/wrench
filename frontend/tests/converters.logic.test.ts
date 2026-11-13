import { describe, expect, it } from 'vitest'
import en from '../src/tools/converters/i18n/en.json'
import fr from '../src/tools/converters/i18n/fr.json'

describe('converters translations', () => {
  it('garde les mêmes clés de grandeur en français et en anglais', () => {
    expect(Object.keys(fr.categories).sort()).toEqual(Object.keys(en.categories).sort())
  })

  it('traduit chaque code d’erreur du service', () => {
    const codes = [
      'unknown_unit',
      'unknown_category',
      'invalid_value',
      'invalid_currency',
      'invalid_rate',
      'invalid_date',
      'unknown_currency',
    ]
    for (const code of codes) {
      expect(fr.errors).toHaveProperty(code)
      expect(en.errors).toHaveProperty(code)
    }
  })
})
