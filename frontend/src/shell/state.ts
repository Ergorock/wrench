import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { getBootstrap, saveSettings, waitForBridge } from '../bridge/client'
import type { Bootstrap, Settings } from '../bridge/types'
import { setLanguage } from '../i18n'
import { applyTheme } from '../theme/theme'
import { buildSidebar, isToolEnabled, type SidebarModel } from './sidebarOrder'
import { toastError } from './toasts'

export interface Shell {
  bootstrap: Ref<Bootstrap | null>
  settings: Ref<Settings>
  view: Ref<'home' | 'settings' | string>
  sidebar: ComputedRef<SidebarModel>
  init(): Promise<void>
  update(mutator: (s: Settings) => void): Promise<void>
  openTool(id: string): void
  toggleFavorite(id: string): void
}

// Placeholder until the bootstrap arrives; the UI renders nothing before that.
const EMPTY_SETTINGS: Settings = {
  schema_version: 1,
  language: 'en',
  theme: 'system',
  autostart: false,
  sidebar: { collapsed: false, category_order: [], tool_order: {}, favorites: [] },
  tools: {},
  window: { x: null, y: null, width: 1100, height: 720, maximized: false },
  last_tool: null,
}

const bootstrap = ref<Bootstrap | null>(null)
const settings = ref<Settings>(EMPTY_SETTINGS)
const view = ref<string>('home')

const sidebar = computed<SidebarModel>(() =>
  bootstrap.value
    ? buildSidebar(bootstrap.value.categories, bootstrap.value.tools, settings.value)
    : { favorites: [], categories: [] },
)

/** Replaces the settings and applies language/theme when they change. */
function apply(next: Settings): void {
  const prev = settings.value
  settings.value = next
  if (next.language !== prev.language) setLanguage(next.language)
  if (next.theme !== prev.theme) applyTheme(next.theme)
}

function isActive(id: string): boolean {
  const tool = bootstrap.value?.tools.find((t) => t.id === id)
  return tool !== undefined && isToolEnabled(tool, settings.value)
}

async function init(): Promise<void> {
  await waitForBridge()
  const b = await getBootstrap()
  bootstrap.value = b
  settings.value = b.settings
  setLanguage(b.settings.language)
  applyTheme(b.settings.theme)
  const last = b.settings.last_tool
  view.value = last && isActive(last) ? last : 'home'
}

// Updates run one after another so each starts from the result of the previous one.
let queue: Promise<void> = Promise.resolve()

function update(mutator: (s: Settings) => void): Promise<void> {
  const task = async (): Promise<void> => {
    const prev = settings.value
    try {
      const draft = JSON.parse(JSON.stringify(prev)) as Settings
      mutator(draft)
      apply(draft) // optimistic, so drag-and-drop does not snap back
      apply(await saveSettings(draft))
    } catch (err) {
      apply(prev)
      toastError(err)
    }
  }
  // The queue never stays rejected, so one failure cannot block later updates.
  queue = queue.then(task).catch(() => {})
  return queue
}

function openTool(id: string): void {
  view.value = id
  if (settings.value.last_tool !== id) {
    void update((s) => {
      s.last_tool = id
    })
  }
}

function toggleFavorite(id: string): void {
  void update((s) => {
    const favs = s.sidebar.favorites
    const i = favs.indexOf(id)
    if (i >= 0) favs.splice(i, 1)
    else favs.push(id)
  })
}

const shell: Shell = { bootstrap, settings, view, sidebar, init, update, openTool, toggleFavorite }

export function useShell(): Shell {
  return shell
}
