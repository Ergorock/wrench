import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import DownloadsCleanerTool from '../src/tools/downloads_cleaner/DownloadsCleanerTool.vue'
import enTool from '../src/tools/downloads_cleaner/i18n/en.json'
import frTool from '../src/tools/downloads_cleaner/i18n/fr.json'

const FOLDER = 'C:/Users/test/Downloads'

const files = [
  { name: 'a.zip', size: 2_000_000, modified: '2026-01-02' },
  { name: 'b.zip', size: 3_000_000, modified: '2026-01-03' },
]

let calls: { action: string; payload?: Record<string, unknown> }[]
let trashFails: string[]
let app: App | null
let host: HTMLElement

beforeEach(() => {
  calls = []
  trashFails = []
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'get_settings') {
          return {
            ok: true,
            data: { folder: FOLDER, extensions: ['zip'], min_age_days: 0, min_size_mb: 0 },
          }
        }
        if (action === 'scan') {
          return { ok: true, data: { folder: FOLDER, files, total_size: 5_000_000 } }
        }
        if (action === 'send_to_trash') {
          const names = payload?.names as string[]
          const removed = names.filter((n) => !trashFails.includes(n))
          const failed = names
            .filter((n) => trashFails.includes(n))
            .map((name) => ({ name, reason: 'delete_failed' }))
          return { ok: true, data: { removed, failed } }
        }
        throw new Error(`unexpected ${action}`)
      },
    },
  }
  setLanguage('en')
})

afterEach(() => {
  app?.unmount()
  app = null
  host?.remove()
  delete (window as unknown as { pywebview?: unknown }).pywebview
  toasts.value = []
})

async function flush(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 10))
  await nextTick()
}

async function mountTool(): Promise<void> {
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(DownloadsCleanerTool).use(i18n)
  app.mount(host)
  await flush()
}

const button = (label: string): HTMLButtonElement =>
  [...host.querySelectorAll('button')].find(
    (b) => b.textContent?.trim() === label,
  ) as HTMLButtonElement

const rows = (): string[] =>
  [...host.querySelectorAll<HTMLElement>('[data-file]')].map((r) => r.dataset.file as string)

async function scanAndWait(): Promise<void> {
  button(enTool.scan).click()
  await flush()
}

describe('DownloadsCleanerTool', () => {
  it('reprend le dernier dossier et les filtres enregistrés', async () => {
    await mountTool()
    expect(calls.map((c) => c.action)).toEqual(['get_settings'])
    expect(host.textContent).toContain(FOLDER)
    const ext = host.querySelector('input') as HTMLInputElement
    expect(ext.value).toBe('zip')
  })

  it('analyse le dossier et sélectionne tous les fichiers trouvés', async () => {
    await mountTool()
    await scanAndWait()
    expect(calls.at(-1)).toMatchObject({
      action: 'scan',
      payload: {
        filters: { folder: FOLDER, extensions: ['zip'], min_age_days: 0, min_size_mb: 0 },
      },
    })
    expect(rows()).toEqual(['a.zip', 'b.zip'])
    const boxes = host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')
    expect([...boxes].every((b) => b.checked)).toBe(true)
  })

  it('demande une confirmation avant d’envoyer quoi que ce soit à la Corbeille', async () => {
    await mountTool()
    await scanAndWait()
    button(enTool.sendToTrash).click()
    await flush()
    expect(calls.some((c) => c.action === 'send_to_trash')).toBe(false)
    expect(host.textContent).toContain('2 file(s)')
    button(enTool.cancel).click()
    await flush()
    expect(calls.some((c) => c.action === 'send_to_trash')).toBe(false)
  })

  it('n’envoie que les fichiers cochés, après confirmation', async () => {
    await mountTool()
    await scanAndWait()
    const boxes = host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')
    boxes[1].click()
    await flush()
    button(enTool.sendToTrash).click()
    await flush()
    button(enTool.confirm).click()
    await flush()
    const trash = calls.find((c) => c.action === 'send_to_trash')
    expect(trash?.payload).toMatchObject({ names: ['a.zip'] })
    expect(rows()).toEqual(['b.zip'])
    expect(host.textContent).toContain(enTool.removedCount.replace('{count}', '1'))
  })

  it('après un envoi, les fichiers restants gardent leur sélection au lieu d’être recochés', async () => {
    await mountTool()
    await scanAndWait()
    const boxes = host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')
    boxes[0].click()
    await flush()
    button(enTool.sendToTrash).click()
    await flush()
    button(enTool.confirm).click()
    await flush()
    const remaining = host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')
    expect(remaining).toHaveLength(1)
    expect(remaining[0].checked).toBe(false)
  })

  it('signale les fichiers qui n’ont pas pu être envoyés', async () => {
    trashFails = ['b.zip']
    await mountTool()
    await scanAndWait()
    button(enTool.sendToTrash).click()
    await flush()
    button(enTool.confirm).click()
    await flush()
    expect(host.textContent).toContain('b.zip : ' + enTool.reasons.delete_failed)
    expect(rows()).toEqual(['b.zip'])
  })

  it('les textes FR et EN ont les mêmes clés de premier niveau', () => {
    expect(Object.keys(frTool).sort()).toEqual(Object.keys(enTool).sort())
  })
})
