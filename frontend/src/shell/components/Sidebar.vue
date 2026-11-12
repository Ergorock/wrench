<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen, Settings, Star } from 'lucide-vue-next'
import type { ToolManifest } from '../../bridge/types'
import type { SidebarModel } from '../sidebarOrder'
import { lucideIcon } from '../icons'
import { useShell } from '../state'
import ContextMenu from './ContextMenu.vue'
import SidebarItem from './SidebarItem.vue'

type CategoryEntry = SidebarModel['categories'][number]

const { t } = useI18n()
const { settings, sidebar, view, update, openTool } = useShell()

const collapsed = computed(() => settings.value.sidebar.collapsed)
const folded = reactive(new Set<string>()) // local, not persisted
const menu = ref<{ x: number; y: number; toolId: string } | null>(null)

const toolName = (id: string) => t(`tools.${id}.name`)

/** Shown ids first, then the saved ids that are not shown (disabled tools, empty categories). */
function merge(shown: string[], saved: string[]): string[] {
  return [...shown, ...saved.filter((id) => !shown.includes(id))]
}

function onFavorites(list: ToolManifest[]): void {
  void update((s) => {
    s.sidebar.favorites = merge(list.map((x) => x.id), s.sidebar.favorites)
  })
}

function onCategories(list: CategoryEntry[]): void {
  void update((s) => {
    s.sidebar.category_order = merge(list.map((c) => c.category.id), s.sidebar.category_order)
  })
}

function onTools(cat: string, list: ToolManifest[]): void {
  void update((s) => {
    s.sidebar.tool_order[cat] = merge(list.map((x) => x.id), s.sidebar.tool_order[cat] ?? [])
  })
}

function toggleFold(id: string): void {
  if (folded.has(id)) folded.delete(id)
  else folded.add(id)
}

function toggleCollapsed(): void {
  void update((s) => {
    s.sidebar.collapsed = !s.sidebar.collapsed
  })
}

function showSettings(): void {
  view.value = 'settings'
}

function openMenu(e: MouseEvent, toolId: string): void {
  menu.value = { x: e.clientX, y: e.clientY, toolId }
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <nav class="scroll">
      <section v-if="sidebar.favorites.length > 0" class="group">
        <div class="group-title" :title="collapsed ? t('nav.favorites') : undefined">
          <Star :size="16" class="muted-icon" />
          <span v-if="!collapsed">{{ t('nav.favorites') }}</span>
        </div>
        <draggable
          :model-value="sidebar.favorites"
          item-key="id"
          group="favorites"
          tag="ul"
          class="list"
          @update:model-value="onFavorites"
        >
          <template #item="{ element }">
            <li>
              <SidebarItem
                :icon="lucideIcon(element.icon)"
                :label="toolName(element.id)"
                :collapsed="collapsed"
                :active="view === element.id"
                @click="openTool(element.id)"
                @contextmenu.prevent="openMenu($event, element.id)"
              />
            </li>
          </template>
        </draggable>
      </section>

      <draggable
        :model-value="sidebar.categories"
        :item-key="(c: CategoryEntry) => c.category.id"
        group="categories"
        handle=".group-title"
        tag="div"
        @update:model-value="onCategories"
      >
        <template #item="{ element: cat }">
          <section class="group">
            <button
              type="button"
              class="group-title"
              :title="collapsed ? t(`categories.${cat.category.id}`) : undefined"
              :aria-label="collapsed ? t(`categories.${cat.category.id}`) : undefined"
              :aria-expanded="!folded.has(cat.category.id)"
              @click="toggleFold(cat.category.id)"
            >
              <component :is="lucideIcon(cat.category.icon)" :size="16" class="muted-icon" />
              <template v-if="!collapsed">
                <span class="title-label">{{ t(`categories.${cat.category.id}`) }}</span>
                <component :is="folded.has(cat.category.id) ? ChevronRight : ChevronDown" :size="14" />
              </template>
            </button>
            <draggable
              v-show="!folded.has(cat.category.id)"
              :model-value="cat.tools"
              item-key="id"
              :group="`tools-${cat.category.id}`"
              tag="ul"
              class="list"
              @update:model-value="(list: ToolManifest[]) => onTools(cat.category.id, list)"
            >
              <template #item="{ element }">
                <li>
                  <SidebarItem
                    :icon="lucideIcon(element.icon)"
                    :label="toolName(element.id)"
                    :collapsed="collapsed"
                    :active="view === element.id"
                    @click="openTool(element.id)"
                    @contextmenu.prevent="openMenu($event, element.id)"
                  />
                </li>
              </template>
            </draggable>
          </section>
        </template>
      </draggable>
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
.scroll {
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
}
.group {
  margin-bottom: 12px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  height: 28px;
  padding: 0 11px;
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
.muted-icon {
  flex: none;
}
.list {
  list-style: none;
  margin: 2px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bottom {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
</style>
