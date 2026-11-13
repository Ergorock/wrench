import { ref, type Ref } from 'vue'
import { getAppIcon } from '../bridge/client'

const RETRY_MS = 30_000
const icons = new Map<string, Ref<string | null>>()
const lastTry = new Map<string, number>()

/**
 * Icon (PNG data URL) of an executable; one bridge call per exe once obtained.
 * A failed or null answer is retried at most every 30 s; no toast.
 */
export function appIcon(exe: string): Ref<string | null> {
  let icon = icons.get(exe)
  if (!icon) {
    icon = ref<string | null>(null)
    icons.set(exe, icon)
  }
  const now = Date.now()
  if (icon.value === null && now - (lastTry.get(exe) ?? -Infinity) >= RETRY_MS) {
    lastTry.set(exe, now)
    const target = icon
    getAppIcon(exe)
      .then((url) => {
        target.value = url
      })
      .catch(() => {})
  }
  return icon
}
