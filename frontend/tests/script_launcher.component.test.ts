import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import { toasts } from '../src/shell/toasts'
import ScriptLauncherTool from '../src/tools/script_launcher/ScriptLauncherTool.vue'
import enTool from '../src/tools/script_launcher/i18n/en.json'

type Cmd = { id: string; name: string; program: string; args: string[]; cwd: string }

let commands: Cmd[]
let calls: { action: string; payload?: Record<string, unknown> }[]
let runResult: unknown
let app: App | null
let host: HTMLElement

beforeEach(() => {
  commands = [{ id: 'c1', name: 'Build', program: 'tool.exe', args: ['--fast'], cwd: '' }]
  calls = []
  runResult = { exit_code: 0, timed_out: false, stdout: 'done\n', stderr: '' }
  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      tool_call: async (_tool: string, action: string, payload?: Record<string, unknown>) => {
        calls.push({ action, payload })
        if (action === 'list_commands') return { ok: true, data: { commands } }
        if (action === 'run_command') return { ok: true, data: runResult }
        if (action === 'delete_command') {
          commands = commands.filter((c) => c.id !== payload?.command_id)
          return { ok: true, data: { commands } }
        }
        if (action === 'save_command') {
          const c = payload?.command as Cmd
          const saved = { ...c, id: c.id || 'new1' }
          commands = c.id ? commands.map((x) => (x.id === c.id ? saved : x)) : [...commands, saved]
          return { ok: true, data: { commands } }
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
  app = createApp(ScriptLauncherTool).use(i18n)
  app.mount(host)
  await flush()
}

const button = (label: string): HTMLButtonElement =>
  [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement

const field = (index: number): HTMLInputElement | HTMLTextAreaElement =>
  host.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('form input, form textarea')[index]

function setValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  el.value = value
  el.dispatchEvent(new Event('input'))
}

describe('ScriptLauncherTool', () => {
  it('liste les commandes enregistrées', async () => {
    await mountTool()
    expect(calls.map((c) => c.action)).toEqual(['list_commands'])
    expect(host.querySelector('[data-command="Build"]')?.textContent).toContain('tool.exe --fast')
  })

  it('lance une commande par son identifiant et affiche la sortie', async () => {
    await mountTool()
    button(enTool.run).click()
    await flush()
    expect(calls.at(-1)).toEqual({ action: 'run_command', payload: { command_id: 'c1' } })
    const out = host.querySelector('[data-testid="output"]')
    expect(out?.textContent).toContain('done')
    expect(out?.textContent).toContain('0')
  })

  it('signale un délai dépassé', async () => {
    runResult = { exit_code: null, timed_out: true, stdout: '', stderr: '' }
    await mountTool()
    button(enTool.run).click()
    await flush()
    expect(host.querySelector('[data-testid="output"]')?.textContent).toContain(enTool.timedOut)
  })

  it('enregistre une nouvelle commande en ignorant les lignes d’arguments vides', async () => {
    await mountTool()
    button(enTool.add).click()
    await nextTick()
    setValue(field(0), 'Nouveau')
    setValue(field(1), 'other.exe')
    setValue(field(2), '-a\n\n  -b  \n')
    host.querySelector('form')!.dispatchEvent(new Event('submit'))
    await flush()
    const save = calls.filter((c) => c.action === 'save_command').at(-1)
    expect(save?.payload).toEqual({
      command: { id: '', name: 'Nouveau', program: 'other.exe', args: ['-a', '-b'], cwd: '' },
    })
    expect(host.querySelector('[data-command="Nouveau"]')).not.toBeNull()
  })

  it('modifie une commande existante sans changer son identifiant', async () => {
    await mountTool()
    button(enTool.edit).click()
    await nextTick()
    expect(field(0).value).toBe('Build')
    expect(field(2).value).toBe('--fast')
    setValue(field(0), 'Build 2')
    host.querySelector('form')!.dispatchEvent(new Event('submit'))
    await flush()
    const save = calls.filter((c) => c.action === 'save_command').at(-1)
    expect((save?.payload?.command as Cmd).id).toBe('c1')
    expect(host.querySelector('[data-command="Build 2"]')).not.toBeNull()
  })

  it('demande une confirmation avant de supprimer', async () => {
    await mountTool()
    button(enTool.delete).click()
    await nextTick()
    expect(calls.some((c) => c.action === 'delete_command')).toBe(false)
    button(enTool.confirmDelete).click()
    await flush()
    expect(calls.at(-1)).toEqual({ action: 'delete_command', payload: { command_id: 'c1' } })
    expect(host.querySelector('[data-command="Build"]')).toBeNull()
  })
})
