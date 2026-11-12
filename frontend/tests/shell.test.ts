import { afterEach, describe, expect, it } from 'vitest'
import { Box, Keyboard, Monitor } from '@lucide/vue'
import { BridgeError } from '../src/bridge/client'
import { useTool } from '../src/bridge/useTool'
import { setLanguage } from '../src/i18n'
import en from '../src/i18n/en.json'
import { lucideIcon } from '../src/shell/icons'
import { useShell } from '../src/shell/state'
import { errorMessage, toasts } from '../src/shell/toasts'

afterEach(() => {
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

describe('lucideIcon', () => {
  it('résout les noms kebab-case et replie sur Box', () => {
    expect(lucideIcon('monitor')).toBe(Monitor)
    expect(lucideIcon('keyboard')).toBe(Keyboard)
    expect(lucideIcon('does-not-exist')).toBe(Box)
  })

  it('connaît les icônes des catégories et de l’outil, et replie sur Box pour un nom inconnu', () => {
    for (const name of ['monitor', 'zap', 'code', 'folder', 'keyboard']) {
      expect(lucideIcon(name), name).not.toBe(Box)
    }
    expect(lucideIcon('')).toBe(Box)
    expect(lucideIcon('box')).toBe(Box)
  })
})

describe('errorMessage', () => {
  it('traduit le code, ou errors.generic si inconnu', () => {
    setLanguage('en')
    expect(errorMessage(new BridgeError('unknown_tool', 'x'))).toBe(en.errors.unknown_tool)
    expect(errorMessage(new BridgeError('no_such_code', 'x'))).toBe(en.errors.generic)
    expect(errorMessage(new Error('x'))).toBe(en.errors.generic)
  })
})

describe('useTool', () => {
  it('affiche un toast puis relance la BridgeError', async () => {
    setLanguage('en')
    ;(window as unknown as { pywebview: unknown }).pywebview = {
      api: { tool_call: async () => ({ ok: false, error: { code: 'invalid_payload', message: 'x' } }) },
    }
    await expect(useTool('t').call('a')).rejects.toBeInstanceOf(BridgeError)
    expect(toasts.value.map((t) => t.message)).toEqual([en.errors.invalid_payload])
  })
})

function bootstrapData() {
  return {
    settings: {
      schema_version: 1,
      language: 'en',
      theme: 'light',
      autostart: false,
      sidebar: { collapsed: false, category_order: [], tool_order: {}, favorites: [] },
      tools: {},
      window: { x: null, y: null, width: 1100, height: 720, maximized: false },
      last_tool: 'a',
    },
    categories: [{ id: 'system', icon: 'monitor' }],
    tools: [{ id: 'a', category: 'system', icon: 'box', version: '1.0.0', enabled_by_default: true }],
    autostart: { available: false, enabled: false },
    warnings: [],
  }
}

describe('useShell', () => {
  it('init rouvre le dernier outil actif, update persiste ou restaure', async () => {
    let fail = false
    ;(window as unknown as { pywebview: unknown }).pywebview = {
      api: {
        get_bootstrap: async () => ({ ok: true, data: bootstrapData() }),
        save_settings: async (s: unknown) =>
          fail ? { ok: false, error: { code: 'invalid_settings', message: 'x' } } : { ok: true, data: s },
      },
    }
    const shell = useShell()
    await shell.init()
    expect(shell.view.value).toBe('a')
    expect(shell.sidebar.value.categories[0].tools.map((t) => t.id)).toEqual(['a'])

    shell.toggleFavorite('a')
    await shell.update(() => {})
    expect(shell.settings.value.sidebar.favorites).toEqual(['a'])

    fail = true
    await shell.update((s) => {
      s.sidebar.favorites = []
    })
    expect(shell.settings.value.sidebar.favorites).toEqual(['a'])
    expect(toasts.value.map((t) => t.message)).toEqual([en.errors.invalid_settings])
  })

  it('un mutator qui lève ne bloque pas les updates suivants', async () => {
    ;(window as unknown as { pywebview: unknown }).pywebview = {
      api: { save_settings: async (s: unknown) => ({ ok: true, data: s }) },
    }
    const shell = useShell()
    await shell.update(() => {
      throw new Error('boom')
    })
    expect(toasts.value.map((t) => t.message)).toEqual([en.errors.generic])
    await shell.update((s) => {
      s.sidebar.collapsed = true
    })
    expect(shell.settings.value.sidebar.collapsed).toBe(true)
  })
})
