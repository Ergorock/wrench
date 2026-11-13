<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { setAutostart } from '../../bridge/client'
import type { Language, ThemePref } from '../../bridge/types'
import { lucideIcon } from '../icons'
import { isToolEnabled } from '../sidebarOrder'
import { useShell } from '../state'
import { toastError } from '../toasts'
import EditorsSettings from './EditorsSettings.vue'
import UpdateSettings from './UpdateSettings.vue'

type Tab = 'general' | 'appearance' | 'tools'

const TABS: Tab[] = ['general', 'appearance', 'tools']
const LANGUAGES: Language[] = ['fr', 'en']
const THEMES: ThemePref[] = ['light', 'dark', 'system']

const { t } = useI18n()
const { bootstrap, settings, view, update } = useShell()
const tab = ref<Tab>('general')

const autostart = computed(() => bootstrap.value?.autostart ?? { available: false, enabled: false })

const toolGroups = computed(() => {
  const b = bootstrap.value
  if (!b) return []
  return b.categories
    .map((category) => ({ category, tools: b.tools.filter((x) => x.category === category.id) }))
    .filter((g) => g.tools.length > 0)
})

function chooseLanguage(lang: Language): void {
  void update((s) => {
    s.language = lang
  })
}

function chooseTheme(theme: ThemePref): void {
  void update((s) => {
    s.theme = theme
  })
}

async function onAutostart(e: Event): Promise<void> {
  const box = e.target as HTMLInputElement
  try {
    const state = await setAutostart(box.checked)
    if (bootstrap.value) bootstrap.value.autostart = state
    // Through the update queue, so an in-flight save cannot bring back the old value.
    void update((s) => {
      s.autostart = state.enabled
    })
  } catch (err) {
    box.checked = autostart.value.enabled
    toastError(err)
  }
}

function setToolEnabled(id: string, enabled: boolean): void {
  void update((s) => {
    s.tools[id] = { enabled }
    if (!enabled) s.sidebar.favorites = s.sidebar.favorites.filter((f) => f !== id)
  })
  if (!enabled && view.value === id) view.value = 'home'
}

const valueOf = (e: Event) => (e.target as HTMLSelectElement).value
const checkedOf = (e: Event) => (e.target as HTMLInputElement).checked
</script>

<template>
  <section class="settings">
    <h1>{{ t('settings.title') }}</h1>

    <div class="tabs" role="tablist">
      <button
        v-for="id in TABS"
        :key="id"
        type="button"
        role="tab"
        class="tab"
        :class="{ selected: tab === id }"
        :aria-selected="tab === id"
        @click="tab = id"
      >
        {{ t(`settings.tabs.${id}`) }}
      </button>
    </div>

    <div v-if="tab === 'general'" class="panel" role="tabpanel">
      <label class="card">
        <span class="card-title">{{ t('settings.language') }}</span>
        <select class="select" :value="settings.language" @change="chooseLanguage(valueOf($event) as Language)">
          <option v-for="lang in LANGUAGES" :key="lang" :value="lang">{{ t(`settings.languages.${lang}`) }}</option>
        </select>
      </label>
      <div class="card">
        <label class="check" :class="{ disabled: !autostart.available }">
          <input
            type="checkbox"
            :checked="autostart.enabled"
            :disabled="!autostart.available"
            @change="onAutostart"
          />
          <span>{{ t('settings.autostart') }}</span>
        </label>
        <p v-if="!autostart.available" class="hint">{{ t('settings.autostartUnavailable') }}</p>
      </div>
      <UpdateSettings />
      <EditorsSettings />
    </div>

    <div v-else-if="tab === 'appearance'" class="panel" role="tabpanel">
      <div class="card" role="radiogroup" :aria-label="t('settings.theme')">
        <span class="card-title">{{ t('settings.theme') }}</span>
        <label v-for="theme in THEMES" :key="theme" class="check">
          <input type="radio" name="theme" :value="theme" :checked="settings.theme === theme" @change="chooseTheme(theme)" />
          <span>{{ t(`settings.themes.${theme}`) }}</span>
        </label>
      </div>
    </div>

    <div v-else class="panel" role="tabpanel">
      <p v-if="toolGroups.length === 0" class="hint">{{ t('settings.noTools') }}</p>
      <section v-for="group in toolGroups" :key="group.category.id">
        <h2>{{ t(`categories.${group.category.id}`) }}</h2>
        <div v-for="tool in group.tools" :key="tool.id" class="card tool">
          <component :is="lucideIcon(tool.icon)" :size="20" class="tool-icon" />
          <div class="tool-text">
            <span class="card-title">{{ t(`tools.${tool.id}.name`) }}</span>
            <span class="hint">{{ t(`tools.${tool.id}.description`) }}</span>
            <span class="hint">{{ t('settings.toolVersion', { version: tool.version }) }}</span>
          </div>
          <input
            type="checkbox"
            role="switch"
            class="switch"
            :aria-label="t(`tools.${tool.id}.name`)"
            :checked="isToolEnabled(tool, settings)"
            @change="setToolEnabled(tool.id, checkedOf($event))"
          />
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.settings {
  max-width: 720px;
}
h1 {
  margin: 0 0 20px;
  font-size: 24px;
  font-weight: 600;
}
h2 {
  margin: 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border);
}
.tab {
  padding: 8px 14px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  cursor: pointer;
}
.tab:hover {
  color: var(--text);
}
.tab.selected {
  color: var(--text);
  border-bottom-color: var(--accent);
  font-weight: 600;
}
.panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.card-title {
  font-weight: 600;
}
.select {
  align-self: flex-start;
  min-width: 200px;
  padding: 6px 10px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 2px);
  font: inherit;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.check.disabled {
  color: var(--text-muted);
  cursor: default;
}
.check input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--accent);
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.4;
}
.tool {
  flex-direction: row;
  align-items: center;
  gap: 14px;
  margin-bottom: 4px;
}
.tool-icon {
  flex: none;
}
.tool-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.switch {
  appearance: none;
  flex: none;
  position: relative;
  width: 40px;
  height: 20px;
  margin: 0;
  border: 1px solid var(--text-muted);
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
}
.switch::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: left 150ms ease;
}
.switch:checked {
  background: var(--accent);
  border-color: var(--accent);
}
.switch:checked::after {
  left: 23px;
  background: var(--accent-text);
}
</style>
