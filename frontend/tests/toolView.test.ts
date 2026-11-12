import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick } from 'vue'
import { i18n, setLanguage } from '../src/i18n'
import en from '../src/i18n/en.json'
import ToolView from '../src/shell/components/ToolView.vue'
import { toolLoaders } from '../src/shell/toolComponents'

afterEach(() => {
  delete toolLoaders.broken
  document.body.innerHTML = ''
})

async function mountToolView(toolId: string): Promise<HTMLElement> {
  const el = document.createElement('div')
  document.body.appendChild(el)
  createApp({ render: () => h(ToolView, { toolId }) })
    .use(i18n)
    .mount(el)
  // Let the async component reject and re-render.
  await new Promise((resolve) => setTimeout(resolve, 20))
  await nextTick()
  return el
}

describe('ToolView', () => {
  it('affiche un message traduit puis l’accueil si le composant ne se charge pas', async () => {
    setLanguage('en')
    toolLoaders.broken = () => Promise.reject(new Error('chunk load failed'))
    const el = await mountToolView('broken')
    expect(el.textContent).toContain(en.errors.toolLoadFailed)
    expect(el.textContent).toContain(en.home.title)
  })

  it('journalise l’erreur de chargement dans la console', async () => {
    setLanguage('en')
    const error = new Error('chunk load failed')
    toolLoaders.broken = () => Promise.reject(error)
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    await mountToolView('broken')
    expect(spy.mock.calls.some((call) => call.includes(error))).toBe(true)
    spy.mockRestore()
  })

  it('propose de réessayer, et affiche l’outil si le second chargement réussit', async () => {
    setLanguage('en')
    let attempts = 0
    toolLoaders.broken = () => {
      attempts += 1
      return attempts === 1
        ? Promise.reject(new Error('chunk load failed'))
        : Promise.resolve({ render: () => h('p', 'Tool loaded') })
    }
    const el = await mountToolView('broken')
    const retry = [...el.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === en.errors.toolLoadRetry,
    )
    expect(retry).toBeDefined()

    retry!.click()
    await new Promise((resolve) => setTimeout(resolve, 20))
    await nextTick()
    expect(attempts).toBe(2)
    expect(el.textContent).toContain('Tool loaded')
    expect(el.textContent).not.toContain(en.errors.toolLoadFailed)
  })

  it('affiche l’accueil si aucun composant n’existe pour cet outil', async () => {
    setLanguage('en')
    const el = await mountToolView('inconnu')
    expect(el.textContent).toContain(en.home.title)
    expect(el.textContent).not.toContain(en.errors.toolLoadFailed)
  })
})
