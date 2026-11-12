import type { ThemePref } from '../bridge/types'

const QUERY = '(prefers-color-scheme: dark)'
let media: MediaQueryList | null = null
let listener: ((e: MediaQueryListEvent) => void) | null = null

function set(dark: boolean): void {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
}

export function applyTheme(pref: ThemePref): void {
  if (media && listener) media.removeEventListener('change', listener)
  media = null
  listener = null
  if (pref === 'system') {
    media = window.matchMedia(QUERY)
    listener = (e) => set(e.matches)
    media.addEventListener('change', listener)
    set(media.matches)
  } else {
    set(pref === 'dark')
  }
}
