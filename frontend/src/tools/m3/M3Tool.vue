<script setup lang="ts">
import { Blocks, Code, FileJson, LayoutGrid } from '@lucide/vue'
import { ref, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { pickFolder } from '../../bridge/client'
import EdaTab from './EdaTab.vue'
import MashupTab from './MashupTab.vue'
import WidgetsTab from './WidgetsTab.vue'
import XtendTab from './XtendTab.vue'
import './m3.css'
import { provideM3 } from './useM3'

const PREFIX = 'tools.m3.'
const { t } = useI18n()
const m3 = provideM3()

const TABS = ['eda', 'mashup', 'widgets', 'xtend'] as const
type TabId = (typeof TABS)[number]

const ICONS: Record<TabId, Component> = {
  eda: FileJson,
  mashup: LayoutGrid,
  widgets: Blocks,
  xtend: Code,
}

// Every tab stays mounted (v-show), so switching tabs keeps what was typed and listed.
const current = ref<TabId>('eda')

async function save(): Promise<void> {
  try {
    await m3.saveConfig()
  } catch {
    // useTool has already shown the error toast.
  }
}

async function chooseOutput(): Promise<void> {
  const picked = await pickFolder(m3.config.value.output_dir || undefined)
  if (picked === null) return
  m3.config.value.output_dir = picked
  await save()
}
</script>

<template>
  <div class="m3 m3-panel">
    <div class="m3-row settings">
      <label class="m3-field">
        {{ t(`${PREFIX}tenant`) }}
        <input v-model="m3.config.value.tenant" type="text" spellcheck="false" @change="save" />
      </label>
      <label class="m3-field grow">
        {{ t(`${PREFIX}outputDir`) }}
        <span class="m3-row">
          <input v-model="m3.config.value.output_dir" type="text" class="grow" @change="save" />
          <button type="button" @click="chooseOutput">{{ t(`${PREFIX}browse`) }}</button>
        </span>
      </label>
    </div>

    <div class="tabs" role="tablist">
      <button
        v-for="tab in TABS"
        :key="tab"
        type="button"
        role="tab"
        class="tab"
        :class="{ active: current === tab }"
        :aria-selected="current === tab"
        @click="current = tab"
      >
        <component :is="ICONS[tab]" :size="16" class="m3-icon" />
        {{ t(`${PREFIX}tabs.${tab}`) }}
      </button>
    </div>

    <section class="m3-card">
      <header class="head">
        <span class="head-icon"><component :is="ICONS[current]" :size="20" /></span>
        <span>
          <h2>{{ t(`${PREFIX}tabs.${current}`) }}</h2>
          <span class="m3-muted">{{ t(`${PREFIX}tabHelp.${current}`) }}</span>
        </span>
      </header>
      <EdaTab v-show="current === 'eda'" />
      <MashupTab v-show="current === 'mashup'" />
      <WidgetsTab v-show="current === 'widgets'" />
      <XtendTab v-show="current === 'xtend'" />
    </section>
  </div>
</template>

<style scoped>
.m3 {
  max-width: 1200px;
  gap: 16px;
}

.grow {
  flex: 1;
  min-width: 0;
}

.settings {
  align-items: flex-end;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--hover);
  border-radius: calc(var(--radius) + 2px);
}

.head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.head h2 {
  margin: 0;
  font-size: 16px;
}

.head-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  border-radius: var(--radius);
}

.tabs .tab {
  flex: 1;
  justify-content: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: none;
  color: var(--text-muted);
  font-weight: 500;
}

.tabs .tab:hover:not(:disabled) {
  background: var(--active);
  color: var(--text);
}

.tabs .tab.active {
  background: var(--bg-elevated);
  border-color: var(--border);
  color: var(--accent);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}
</style>
