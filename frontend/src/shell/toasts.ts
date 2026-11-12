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

/** Translated message for a bridge error: `errors.<code>`, or `errors.generic` if unknown. */
export function errorMessage(err: unknown): string {
  const key = err instanceof BridgeError ? `errors.${err.code}` : 'errors.generic'
  return i18n.global.t(i18n.global.te(key) ? key : 'errors.generic')
}

export function toastError(err: unknown): void {
  pushToast(errorMessage(err), 'error')
}
