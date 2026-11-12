import { ref } from 'vue'
import { BridgeError } from '../bridge/client'
import { i18n } from '../i18n'

export interface Toast {
  id: number
  message: string
  kind: 'error' | 'info'
}

const DURATION_MS = 5000

export const toasts = ref<Toast[]>([])
let nextId = 0

export function pushToast(message: string, kind: 'error' | 'info' = 'error'): void {
  const id = nextId++
  toasts.value.push({ id, message, kind })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, DURATION_MS)
}

/**
 * Translated message for a bridge error. Lookup order: `tools.<toolId>.errors.<code>` (only when
 * `toolId` is given), then `errors.<code>`, then `errors.generic`.
 */
export function errorMessage(err: unknown, toolId?: string): string {
  if (err instanceof BridgeError) {
    const candidates = [...(toolId ? [`tools.${toolId}.errors.${err.code}`] : []), `errors.${err.code}`]
    const key = candidates.find((k) => i18n.global.te(k))
    if (key) return i18n.global.t(key)
  }
  return i18n.global.t('errors.generic')
}

export function toastError(err: unknown, toolId?: string): void {
  pushToast(errorMessage(err, toolId), 'error')
}
