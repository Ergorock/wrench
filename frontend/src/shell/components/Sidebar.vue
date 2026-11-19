<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import {
  ChevronDown,
  ChevronRight,
  GripVertical,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
} from '@lucide/vue'
import type { ToolManifest } from '../../bridge/types'
import { matchesQuery, type SidebarModel } from '../sidebarOrder'
import { lucideIcon } from '../icons'
import { useShell } from '../state'
import ContextMenu from './ContextMenu.vue'
import SidebarItem from './SidebarItem.vue'

type CategoryEntry = SidebarModel['categories'][number]

const { t } = useI18n()
const { settings, sidebar, view, update, openTool, toggleFavorite } = useShell()

const collapsed = computed(() => settings.value.sidebar.collapsed)
const folded = computed(() => new Set(settings.value.sidebar.folded))
const menu = ref<{ x: number; y: number; toolId: string } | null>(null)
const nav = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const query = ref('')
const selected = ref(0)

/** The open tool is already highlighted in its category, so it is left out of the recents. */
const recents = computed(() => sidebar.value.recents.filter((x) => x.id !== view.value))

const toolName = (id: string) => t(`tools.${id}.name`)
const isFavorite = (id: string) => settings.value.sidebar.favorites.includes(id)
const starLabel = (id: string) => t(isFavorite(id) ? 'nav.unpin' : 'nav.pin')
/** Folding only applies to the full menu: the icon rail always shows every tool. */
const isFolded = (catId: string) => !collapsed.value && folded.value.has(catId)

const results = computed(() =>
  query.value.trim() === ''
    ? []
    : sidebar.value.categories.flatMap((c) =>
        c.tools.filter((tool) =>
          matchesQuery(`${toolName(tool.id)} ${t(`categories.${c.category.id}`)}`, query.value),
        ),
      ),
)
watch(query, () => {
  selected.value = 0
})

/** Shown ids first, then the saved ids that are not shown (disabled tools, empty categories). */
function merge(shown: string[], saved: string[]): string[] {
  return [...shown, ...saved.filter((id) => !shown.includes(id))]
}

function setFavorites(ids: string[]): Promise<void> {
  return update((s) => {
    s.sidebar.favorites = merge(ids, s.sidebar.favorites)
  })
}

function setCategories(ids: string[]): void {
  void update((s) => {
    s.sidebar.category_order = merge(ids, s.sidebar.category_order)
  })
}

function setTools(cat: string, ids: string[]): Promise<void> {
  return update((s) => {
    s.sidebar.tool_order[cat] = merge(ids, s.sidebar.tool_order[cat] ?? [])
  })
}

const ids = (list: ToolManifest[]) => list.map((x) => x.id)

function toggleFold(id: string): void {
  void update((s) => {
    const list = s.sidebar.folded
    const i = list.indexOf(id)
    if (i >= 0) list.splice(i, 1)
    else list.push(id)
  })
}

function toggleCollapsed(): Promise<void> {
  return update((s) => {
    s.sidebar.collapsed = !s.sidebar.collapsed
  })
}

function showSettings(): void {
  view.value = 'settings'
}

function openMenu(e: MouseEvent, toolId: string): void {
  menu.value = { x: e.clientX, y: e.clientY, toolId }
}

// --- Search -------------------------------------------------------------

async function focusSearch(): Promise<void> {
  if (collapsed.value) {
    await toggleCollapsed()
    await nextTick()
  }
  searchInput.value?.focus()
  searchInput.value?.select()
}

function clearSearch(): void {
  query.value = ''
}

function openResult(tool: ToolManifest): void {
  openTool(tool.id)
  clearSearch()
}

function onSearchKey(e: KeyboardEvent): void {
  const last = results.value.length - 1
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (query.value.trim() === '') navButtons()[0]?.focus()
    else selected.value = Math.min(selected.value + 1, last)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selected.value = Math.max(selected.value - 1, 0)
  } else if (e.key === 'Enter') {
    const hit = results.value[selected.value]
    if (hit) openResult(hit)
  } else if (e.key === 'Escape') {
    clearSearch()
    searchInput.value?.blur()
  }
}

function onGlobalKey(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    void focusSearch()
  }
}
onMounted(() => window.addEventListener('keydown', onGlobalKey))
onUnmounted(() => window.removeEventListener('keydown', onGlobalKey))

// --- Keyboard navigation in the list ------------------------------------

function navButtons(): HTMLElement[] {
  return Array.from(nav.value?.querySelectorAll<HTMLElement>('.item, button.group-title') ?? [])
}

/** Alt+Up / Alt+Down: moves a tool one place within its list (favorites or its category). */
function moveTool(row: HTMLElement, delta: number): void {
  const { tool, list } = row.dataset
  if (!tool || !list) return
  const order = list === 'fav'
    ? ids(sidebar.value.favorites)
    : ids(sidebar.value.categories.find((c) => `cat:${c.category.id}` === list)?.tools ?? [])
  const from = order.indexOf(tool)
  const to = from + delta
  if (from < 0 || to < 0 || to >= order.length) return
  ;[order[from], order[to]] = [order[to], order[from]]
  const done = list === 'fav' ? setFavorites(order) : setTools(list.slice(4), order)
  void done.then(() => nextTick()).then(() => {
    nav.value
      ?.querySelector<HTMLElement>(`[data-list="${list}"][data-tool="${tool}"] .item`)
      ?.focus()
  })
}

function onNavKey(e: KeyboardEvent): void {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
  const target = e.target as HTMLElement
  const delta = e.key === 'ArrowDown' ? 1 : -1
  e.preventDefault()
  if (e.altKey) {
    const row = target.closest<HTMLElement>('[data-tool]')
    if (row) moveTool(row, delta)
    return
  }
  const buttons = navButtons()
  const at = buttons.indexOf(target.closest('.item, button.group-title') as HTMLElement)
  if (at < 0) return
  if (at + delta < 0) searchInput.value?.focus()
  else buttons[Math.min(at + delta, buttons.length - 1)]?.focus()
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="top">
      <label v-if="!collapsed" class="search">
        <Search :size="16" class="search-icon" />
        <input
          ref="searchInput"
          v-model="query"
          type="text"
          :placeholder="t('nav.search')"
          :aria-label="t('nav.search')"
          autocomplete="off"
          spellcheck="false"
          @keydown="onSearchKey"
        />
        <kbd v-if="query === ''" class="hint">Ctrl K</kbd>
      </label>
      <SidebarItem v-else :icon="Search" :label="t('nav.search')" collapsed @click="focusSearch" />
    </div>

    <nav ref="nav" class="scroll" @keydown="onNavKey">
      <template v-if="query.trim() !== ''">
        <ul v-if="results.length > 0" class="list">
          <li v-for="(tool, i) in results" :key="tool.id">
            <SidebarItem
              :icon="lucideIcon(tool.icon)"
              :label="toolName(tool.id)"
              :collapsed="false"
              :active="view === tool.id"
              :highlighted="i === selected"
              @click="openResult(tool)"
            />
          </li>
        </ul>
        <p v-else class="empty">{{ t('nav.noResults') }}</p>
      </template>

      <template v-else>
        <section v-if="sidebar.favorites.length > 0" class="group">
          <div v-if="!collapsed" class="group-title">
            <span>{{ t('nav.favorites') }}</span>
          </div>
          <draggable
            :model-value="sidebar.favorites"
            item-key="id"
            group="favorites"
            tag="ul"
            class="list"
            @update:model-value="(list: ToolManifest[]) => void setFavorites(ids(list))"
          >
            <template #item="{ element }">
              <li>
                <SidebarItem
                  data-list="fav"
                  :data-tool="element.id"
                  :icon="lucideIcon(element.icon)"
                  :label="toolName(element.id)"
                  :collapsed="collapsed"
                  :active="view === element.id"
                  :star-label="starLabel(element.id)"
                  :starred="true"
                  @click="openTool(element.id)"
                  @star="toggleFavorite(element.id)"
                  @contextmenu.prevent="openMenu($event, element.id)"
                />
              </li>
            </template>
          </draggable>
        </section>

        <section v-if="recents.length > 0" class="group">
          <div v-if="!collapsed" class="group-title">
            <span>{{ t('nav.recents') }}</span>
          </div>
          <ul class="list">
            <li v-for="tool in recents" :key="tool.id">
              <SidebarItem
                data-list="recent"
                :data-tool="tool.id"
                :icon="lucideIcon(tool.icon)"
                :label="toolName(tool.id)"
                :collapsed="collapsed"
                :active="view === tool.id"
                :star-label="starLabel(tool.id)"
                :starred="false"
                @click="openTool(tool.id)"
                @star="toggleFavorite(tool.id)"
                @contextmenu.prevent="openMenu($event, tool.id)"
              />
            </li>
          </ul>
        </section>

        <draggable
          :model-value="sidebar.categories"
          :item-key="(c: CategoryEntry) => c.category.id"
          group="categories"
          handle=".grip"
          tag="div"
          @update:model-value="(list: CategoryEntry[]) => setCategories(list.map((c) => c.category.id))"
        >
          <template #item="{ element: cat }">
            <section class="group">
              <div v-if="!collapsed" class="title-row">
                <span class="grip" aria-hidden="true"><GripVertical :size="12" /></span>
                <button
                  type="button"
                  class="group-title"
                  :aria-expanded="!isFolded(cat.category.id)"
                  @click="toggleFold(cat.category.id)"
                >
                  <span class="title-label">{{ t(`categories.${cat.category.id}`) }}</span>
                  <component :is="isFolded(cat.category.id) ? ChevronRight : ChevronDown" :size="14" />
                </button>
              </div>
              <draggable
                v-if="!isFolded(cat.category.id)"
                :model-value="cat.tools"
                item-key="id"
                :group="`tools-${cat.category.id}`"
                tag="ul"
                class="list"
                @update:model-value="(list: ToolManifest[]) => void setTools(cat.category.id, ids(list))"
              >
                <template #item="{ element }">
                  <li>
                    <SidebarItem
                      :data-list="`cat:${cat.category.id}`"
                      :data-tool="element.id"
                      :icon="lucideIcon(element.icon)"
                      :label="toolName(element.id)"
                      :collapsed="collapsed"
                      :active="view === element.id"
                      :star-label="starLabel(element.id)"
                      :starred="isFavorite(element.id)"
                      @click="openTool(element.id)"
                      @star="toggleFavorite(element.id)"
                      @contextmenu.prevent="openMenu($event, element.id)"
                    />
                  </li>
                </template>
              </draggable>
            </section>
          </template>
        </draggable>
      </template>
    </nav>

    <div class="bottom">
      <SidebarItem
        :icon="Settings"
        :label="t('nav.settings')"
        :collapsed="collapsed"
        :active="view === 'settings'"
        @click="showSettings"
      />
      <SidebarItem
        :icon="collapsed ? PanelLeftOpen : PanelLeftClose"
        :label="t(collapsed ? 'nav.expand' : 'nav.collapse')"
        :collapsed="collapsed"
        @click="toggleCollapsed"
      />
    </div>

    <ContextMenu v-if="menu" v-bind="menu" @close="menu = null" />
  </aside>
</template>

<style scoped>
.sidebar {
  flex: none;
  display: flex;
  flex-direction: column;
  width: 240px;
  height: 100vh;
  box-sizing: border-box;
  padding: 12px 8px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  transition: width 150ms ease;
  overflow: hidden;
}
.sidebar.collapsed {
  width: 56px;
}
.top {
  padding-bottom: 8px;
}
.search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 10px;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text-muted);
}
.search:focus-within {
  border-color: var(--accent);
  outline: 1px solid var(--accent);
}
.search input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font: inherit;
}
.search-icon {
  flex: none;
}
.hint {
  padding: 1px 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font: inherit;
  font-size: 11px;
  white-space: nowrap;
}
.scroll {
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
}
.group {
  margin-bottom: 14px;
}
.sidebar.collapsed .group + .group {
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.title-row {
  position: relative;
}
.grip {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 11px;
  color: var(--text-muted);
  cursor: grab;
  opacity: 0;
}
.title-row:hover .grip {
  opacity: 1;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 28px;
  padding: 0 10px 0 14px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}
button.group-title {
  cursor: pointer;
}
button.group-title:hover {
  background: var(--hover);
}
.title-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
.list {
  list-style: none;
  margin: 2px 0 0;
  padding: 2px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.empty {
  margin: 8px 11px;
  color: var(--text-muted);
}
.bottom {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
</style>
