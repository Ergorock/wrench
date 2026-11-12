import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Settings, UpdateStatus } from '../src/bridge/types'
import { _resetUpdatesForTests, shouldAutoCheck, useUpdates } from '../src/shell/updates'
import { toasts } from '../src/shell/toasts'

type Api = Record<string, (...args: unknown[]) => Promise<unknown>>

function mockApi(api: Api) {
  ;(window as unknown as { pywebview?: { api: Api } }).pywebview = { api }
}

const INFO = {
  version: '1.3.0',
  notes_url: 'https://github.com/Ergorock/wrench/releases/tag/v1.3.0',
  asset_url: 'https://github.com/Ergorock/wrench/releases/download/v1.3.0/Wrench-Setup-1.3.0.exe',
  size: 10,
  sha256: 'a',
}

function st(over: Partial<UpdateStatus> = {}): UpdateStatus {
  return { supported: true, current_version: '1.2.0', status: 'idle', info: null, progress: 0, error_code: null, ...over }
}

const ok = <T>(data: T) => ({ ok: true, data })
const fail = (code: string) => ({ ok: false, error: { code, message: 'x' } })

const s = (u: Partial<Settings['updates']> = {}) =>
  ({ updates: { auto_check: true, last_check: null, ...u } }) as Settings

beforeEach(() => {
  vi.useFakeTimers()
  _resetUpdatesForTests()
  toasts.value = []
})

afterEach(() => {
  _resetUpdatesForTests()
  vi.useRealTimers()
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

describe('shouldAutoCheck', () => {
  const now = new Date('2026-11-12T12:00:00Z')
  it('vérifie si jamais vérifié', () => expect(shouldAutoCheck(s({ last_check: null }), true, now)).toBe(true))
  it('ne vérifie pas avant 24 h', () =>
    expect(shouldAutoCheck(s({ last_check: '2026-11-12T00:00:00Z' }), true, now)).toBe(false))
  it('vérifie après 24 h', () =>
    expect(shouldAutoCheck(s({ last_check: '2026-11-11T11:00:00Z' }), true, now)).toBe(true))
  it('jamais si désactivé ou non supporté', () => {
    expect(shouldAutoCheck(s({ auto_check: false, last_check: null }), true, now)).toBe(false)
    expect(shouldAutoCheck(s({ last_check: null }), false, now)).toBe(false)
  })
})

describe('useUpdates', () => {
  it('Plus tard masque le bandeau', async () => {
    mockApi({ check_for_updates: async () => ok(st({ status: 'available', info: INFO })) })
    const u = useUpdates()
    await u.checkNow()
    expect(u.bannerVisible.value).toBe(true)
    u.dismiss()
    expect(u.bannerVisible.value).toBe(false)
  })

  it("une erreur de vérification automatique n'affiche pas de toast", async () => {
    mockApi({
      get_update_status: async () => fail('internal_error'),
      check_for_updates: async () => fail('update_network'),
    })
    const u = useUpdates()
    u.startAutoCheck(s())
    await vi.advanceTimersByTimeAsync(0)
    expect(toasts.value).toEqual([])
    expect(u.bannerVisible.value).toBe(false)
  })

  it('une vérification automatique en échec (statut error) reste silencieuse et sans bandeau', async () => {
    mockApi({
      get_update_status: async () => ok(st()),
      check_for_updates: async () => ok(st({ status: 'error', error_code: 'update_network' })),
    })
    const u = useUpdates()
    u.startAutoCheck(s())
    await vi.advanceTimersByTimeAsync(0)
    expect(u.status.value.status).toBe('error')
    expect(toasts.value).toEqual([])
    expect(u.bannerVisible.value).toBe(false)
  })

  it('checkNow affiche un toast sur une erreur de pont ou un statut error', async () => {
    mockApi({ check_for_updates: async () => fail('update_unsupported') })
    const u = useUpdates()
    await u.checkNow()
    expect(toasts.value).toHaveLength(1)
    toasts.value = []
    mockApi({ check_for_updates: async () => ok(st({ status: 'error', error_code: 'update_network' })) })
    await u.checkNow()
    expect(toasts.value).toHaveLength(1)
  })

  it("le minuteur de 24 h n'est démarré qu'une fois", async () => {
    const check = vi.fn(async () => ok(st({ status: 'up_to_date' })))
    mockApi({ get_update_status: async () => ok(st()), check_for_updates: check })
    const u = useUpdates()
    u.startAutoCheck(s())
    u.startAutoCheck(s())
    await vi.advanceTimersByTimeAsync(0)
    expect(check).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(24 * 3600 * 1000)
    expect(check).toHaveBeenCalledTimes(2)
  })

  it('install interroge toutes les 500 ms : downloading, installing, puis arrêt', async () => {
    const seq = [
      st({ status: 'downloading', progress: 0.5, info: INFO }),
      st({ status: 'installing', progress: 1, info: INFO }),
      st({ status: 'up_to_date' }),
    ]
    const poll = vi.fn(async () => ok(seq.shift() ?? st({ status: 'up_to_date' })))
    mockApi({
      install_update: async () => ok(st({ status: 'downloading', info: INFO })),
      get_update_status: poll,
    })
    const u = useUpdates()
    await u.install()
    expect(u.status.value.status).toBe('downloading')
    expect(u.bannerVisible.value).toBe(true)
    await vi.advanceTimersByTimeAsync(500)
    expect(u.status.value.progress).toBe(0.5)
    await vi.advanceTimersByTimeAsync(500)
    expect(u.status.value.status).toBe('installing')
    await vi.advanceTimersByTimeAsync(500)
    expect(u.status.value.status).toBe('up_to_date')
    await vi.advanceTimersByTimeAsync(2000)
    expect(poll).toHaveBeenCalledTimes(3)
  })

  it('une erreur de téléchargement après un clic affiche le bandeau', async () => {
    mockApi({
      install_update: async () => ok(st({ status: 'downloading', info: INFO })),
      get_update_status: async () => ok(st({ status: 'error', error_code: 'update_integrity', info: INFO })),
    })
    const u = useUpdates()
    await u.install()
    await vi.advanceTimersByTimeAsync(500)
    expect(u.status.value.status).toBe('error')
    expect(u.bannerVisible.value).toBe(true)
  })

  it('install : erreur de pont, toast et pas de sondage', async () => {
    const poll = vi.fn(async () => ok(st()))
    mockApi({ install_update: async () => fail('no_update'), get_update_status: poll })
    const u = useUpdates()
    await u.install()
    await vi.advanceTimersByTimeAsync(1500)
    expect(toasts.value).toHaveLength(1)
    expect(poll).not.toHaveBeenCalled()
  })
})
