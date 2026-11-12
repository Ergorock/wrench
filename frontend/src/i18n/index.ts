import { createI18n } from 'vue-i18n'
import type { Language } from '../bridge/types'
import en from './en.json'
import fr from './fr.json'

const toolModules = import.meta.glob('../tools/*/i18n/*.json', {
  eager: true,
  import: 'default',
}) as Record<string, object>

const toolMessages: Record<Language, Record<string, object>> = { fr: {}, en: {} }
for (const [path, msgs] of Object.entries(toolModules)) {
  const m = /\.\.\/tools\/([^/]+)\/i18n\/([^/]+)\.json$/.exec(path)
  if (m && (m[2] === 'fr' || m[2] === 'en')) toolMessages[m[2]][m[1]] = msgs
}

const messages = {
  fr: { ...fr, tools: toolMessages.fr },
  en: { ...en, tools: toolMessages.en },
}

export const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages,
})

export function setLanguage(lang: Language): void {
  i18n.global.locale.value = lang
  document.documentElement.lang = lang
}
