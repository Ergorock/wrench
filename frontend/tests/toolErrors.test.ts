import { afterEach, describe, expect, it } from 'vitest'
import { BridgeError } from '../src/bridge/client'
import { useTool } from '../src/bridge/useTool'
import { i18n, setLanguage } from '../src/i18n'
import en from '../src/i18n/en.json'
import { errorMessage, toasts } from '../src/shell/toasts'

afterEach(() => {
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

describe('errorMessage avec toolId', () => {
  it('préfère tools.<id>.errors.<code>, puis errors.<code>, puis errors.generic', () => {
    setLanguage('en')
    i18n.global.mergeLocaleMessage('en', {
      tools: { demo: { errors: { custom_code: 'Message propre à l’outil', unknown_tool: 'Surcharge outil' } } },
    })

    expect(errorMessage(new BridgeError('custom_code', 'x'), 'demo')).toBe('Message propre à l’outil')
    expect(errorMessage(new BridgeError('unknown_tool', 'x'), 'demo')).toBe('Surcharge outil')
    expect(errorMessage(new BridgeError('invalid_payload', 'x'), 'demo')).toBe(en.errors.invalid_payload)
    expect(errorMessage(new BridgeError('no_such_code', 'x'), 'demo')).toBe(en.errors.generic)
    expect(errorMessage(new Error('x'), 'demo')).toBe(en.errors.generic)
  })

  it('sans toolId, garde le comportement existant', () => {
    setLanguage('en')
    expect(errorMessage(new BridgeError('unknown_tool', 'x'))).toBe(en.errors.unknown_tool)
    expect(errorMessage(new BridgeError('custom_code', 'x'))).toBe(en.errors.generic)
  })

  it('un outil sans traduction propre retombe sur errors.<code>', () => {
    setLanguage('en')
    expect(errorMessage(new BridgeError('unknown_tool', 'x'), 'autre_outil')).toBe(en.errors.unknown_tool)
  })
})

describe('useTool transmet son toolId au toast', () => {
  it('affiche la traduction propre à l’outil', async () => {
    setLanguage('en')
    i18n.global.mergeLocaleMessage('en', { tools: { demo: { errors: { custom_code: 'Message propre à l’outil' } } } })
    ;(window as unknown as { pywebview: unknown }).pywebview = {
      api: { tool_call: async () => ({ ok: false, error: { code: 'custom_code', message: 'x' } }) },
    }
    await expect(useTool('demo').call('a')).rejects.toBeInstanceOf(BridgeError)
    expect(toasts.value.map((t) => t.message)).toEqual(['Message propre à l’outil'])
  })
})
