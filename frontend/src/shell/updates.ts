import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { BridgeError, checkForUpdates, getUpdateStatus, installUpdate } from '../bridge/client'
import type { Settings, UpdateStatus } from '../bridge/types'
import { i18n } from '../i18n'
import { pushToast, toastError } from './toasts'

const DAY_MS = 24 * 3600 * 1000
const POLL_MS = 500

export interface Updates {
  status: Ref<UpdateStatus>
  bannerVisible: ComputedRef<boolean>
  startAutoCheck(settings: Settings): void
  checkNow(): Promise<UpdateStatus>
  install(): Promise<void>
  dismiss(): void
}

/** True when automatic checks are on, supported, and the last check is missing or over 24 h old. */
export function shouldAutoCheck(settings: Settings, supported: boolean, now: Date): boolean {
  if (!supported || !settings.updates.auto_check) return false
  const last = settings.updates.last_check
  if (last === null) return true
  const ts = Date.parse(last)
  return Number.isNaN(ts) || now.getTime() - ts > DAY_MS
}

const INITIAL: UpdateStatus = {
  supported: true,
  current_version: '',
  status: 'idle',
  info: null,
  progress: 0,
  error_code: null,
}

const status = ref<UpdateStatus>({ ...INITIAL })
const dismissed = ref(false)
// Set by a click on "Mettre à jour": only then do downloading/installing/error show the banner.
const installRequested = ref(false)
let started = false
let dailyTimer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const bannerVisible = computed(() => {
  if (dismissed.value) return false
  const s = status.value.status
  if (s === 'available') return true
  return installRequested.value && (s === 'downloading' || s === 'installing' || s === 'error')
})

/** Reports an error status to the user; the generic message when the code is unknown. */
function notifyStatusError(s: UpdateStatus): void {
  const key = `errors.${s.error_code}`
  pushToast(i18n.global.te(key) ? i18n.global.t(key) : i18n.global.t('errors.generic'), 'error')
}

function stopPolling(): void {
  if (pollTimer !== null) clearInterval(pollTimer)
  pollTimer = null
}

function isBusy(s: UpdateStatus): boolean {
  return s.status === 'downloading' || s.status === 'installing'
}

function startPolling(): void {
  stopPolling()
  let inFlight = false
  pollTimer = setInterval(async () => {
    if (inFlight) return
    inFlight = true
    try {
      status.value = await getUpdateStatus()
      if (!isBusy(status.value)) stopPolling()
    } catch {
      stopPolling()
    } finally {
      inFlight = false
    }
  }, POLL_MS)
}

async function silentCheck(): Promise<void> {
  try {
    status.value = await checkForUpdates()
  } catch {
    // Automatic checks fail silently.
  }
}

function startAutoCheck(settings: Settings): void {
  if (started) return
  started = true
  void (async () => {
    try {
      const current = await getUpdateStatus()
      status.value = current
      if (!current.supported) return
      dailyTimer = setInterval(() => void silentCheck(), DAY_MS)
      if (shouldAutoCheck(settings, current.supported, new Date())) await silentCheck()
    } catch {
      // Never throws, never toasts.
    }
  })()
}

async function checkNow(): Promise<UpdateStatus> {
  try {
    const next = await checkForUpdates()
    status.value = next
    if (next.status === 'error') notifyStatusError(next)
  } catch (err) {
    toastError(err)
    // Keeps a visible result in the settings section even when the envelope failed.
    status.value = { ...status.value, status: 'error', error_code: err instanceof BridgeError ? err.code : null }
  }
  return status.value
}

async function install(): Promise<void> {
  installRequested.value = true
  try {
    status.value = await installUpdate()
    if (isBusy(status.value)) startPolling()
  } catch (err) {
    toastError(err)
  }
}

function dismiss(): void {
  dismissed.value = true
}

/** Test-only: restores the initial singleton state and clears timers. */
export function _resetUpdatesForTests(): void {
  stopPolling()
  if (dailyTimer !== null) clearInterval(dailyTimer)
  dailyTimer = null
  started = false
  dismissed.value = false
  installRequested.value = false
  status.value = { ...INITIAL }
}

const updates: Updates = { status, bannerVisible, startAutoCheck, checkNow, install, dismiss }

export function useUpdates(): Updates {
  return updates
}
