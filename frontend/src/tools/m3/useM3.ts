import { inject, onBeforeUnmount, provide, ref, type InjectionKey, type Ref } from 'vue'
import { BridgeError } from '../../bridge/client'
import { useTool } from '../../bridge/useTool'
import { toastError } from '../../shell/toasts'
import type { Config, JobView, State } from './types'

const POLL_MS = 600

export interface M3 {
  state: Ref<State | null>
  /** Editable copy of the saved settings. */
  config: Ref<Config>
  call<T>(action: string, payload?: object): Promise<T>
  saveConfig(): Promise<void>
  refresh(): Promise<void>
  /** Runs `cb` each time a background job ends (success, error or cancel). Returns the unsubscriber. */
  onJobEnd(cb: (job: JobView) => void): () => void
}

const KEY: InjectionKey<M3> = Symbol('m3')

const EMPTY_CONFIG: Config = {
  tenant: '',
  eda_base_url: '',
  company: '',
  division: '',
  language: '',
  output_dir: '',
}

export function provideM3(): M3 {
  const tool = useTool('m3')
  const state = ref<State | null>(null)
  const config = ref<Config>({ ...EMPTY_CONFIG })
  const listeners = new Set<(job: JobView) => void>()
  let timer: ReturnType<typeof setInterval> | null = null
  let wasRunning = false
  let loaded = false
  let disposed = false

  function stopPolling(): void {
    if (timer !== null) clearInterval(timer)
    timer = null
  }

  async function refresh(): Promise<void> {
    let next: State
    try {
      next = await tool.call<State>('get_state')
    } catch {
      return // useTool has already shown the error toast
    }
    if (disposed) return
    state.value = next
    if (!loaded) {
      config.value = { ...next.config }
      loaded = true
    }
    const job = next.job
    if (job.running && timer === null) timer = setInterval(() => void refresh(), POLL_MS)
    if (!job.running) stopPolling()
    if (wasRunning && !job.running) {
      if (job.error) toastError(new BridgeError(job.error.code, job.error.message), 'm3')
      listeners.forEach((cb) => cb(job))
    }
    wasRunning = job.running
  }

  async function call<T>(action: string, payload?: object): Promise<T> {
    try {
      return await tool.call<T>(action, payload)
    } finally {
      await refresh()
    }
  }

  async function saveConfig(): Promise<void> {
    config.value = await call<Config>('set_config', { ...config.value })
  }

  const m3: M3 = {
    state,
    config,
    call,
    saveConfig,
    refresh,
    onJobEnd(cb) {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
  }
  provide(KEY, m3)
  onBeforeUnmount(() => {
    disposed = true
    stopPolling()
  })
  void refresh()
  return m3
}

export function useM3(): M3 {
  const m3 = inject(KEY)
  if (!m3) throw new Error('useM3 called outside M3Tool')
  return m3
}
