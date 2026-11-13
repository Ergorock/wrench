import { ref, type Ref } from 'vue'
import { getAppIcon } from '../bridge/client'

const icons = new Map<string, Ref<string | null>>()

/** Icon (PNG data URL) of an executable; one bridge call per exe, null on failure, no toast. */
export function appIcon(exe: string): Ref<string | null> {
  let icon = icons.get(exe)
  if (!icon) {
    const target = ref<string | null>(null)
    icon = target
    icons.set(exe, target)
    getAppIcon(exe)
      .then((url) => {
        target.value = url
      })
      .catch(() => {})
  }
  return icon
}
