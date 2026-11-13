import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getAppIcon = vi.fn<(exe: string) => Promise<string | null>>()
vi.mock('../src/bridge/client', () => ({ getAppIcon: (exe: string) => getAppIcon(exe) }))

import { appIcon } from '../src/shell/appIcons'

beforeEach(() => {
  vi.useFakeTimers()
  getAppIcon.mockReset()
})
afterEach(() => vi.useRealTimers())

describe('appIcon retry', () => {
  it('relance après 30 s un appel en échec, pas avant', async () => {
    getAppIcon.mockResolvedValueOnce(null).mockResolvedValueOnce('data:ok')
    const icon = appIcon('fail.exe')
    await vi.advanceTimersByTimeAsync(0)
    expect(getAppIcon).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(29_000)
    appIcon('fail.exe')
    expect(getAppIcon).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(1_000)
    appIcon('fail.exe')
    await vi.advanceTimersByTimeAsync(0)
    expect(getAppIcon).toHaveBeenCalledTimes(2)
    expect(icon.value).toBe('data:ok')
  })

  it('ne redemande pas une icône obtenue', async () => {
    getAppIcon.mockResolvedValue('data:ok')
    appIcon('ok.exe')
    await vi.advanceTimersByTimeAsync(0)
    vi.advanceTimersByTime(120_000)
    appIcon('ok.exe')
    expect(getAppIcon).toHaveBeenCalledTimes(1)
  })

  it('deux appels dans les 30 s après un échec ne font pas de seconde requête', async () => {
    getAppIcon.mockRejectedValue(new Error('x'))
    appIcon('rej.exe')
    await vi.advanceTimersByTimeAsync(0)
    vi.advanceTimersByTime(5_000)
    appIcon('rej.exe')
    appIcon('rej.exe')
    expect(getAppIcon).toHaveBeenCalledTimes(1)
  })
})
