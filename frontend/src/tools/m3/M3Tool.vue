<script setup lang="ts">
import { ref } from 'vue'
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
        {{ t(`${PREFIX}tabs.${tab}`) }}
      </button>
    </div>

    <EdaTab v-show="current === 'eda'" />
    <MashupTab v-show="current === 'mashup'" />
    <WidgetsTab v-show="current === 'widgets'" />
    <XtendTab v-show="current === 'xtend'" />
  </div>
</template>

<style scoped>
.m3 {
  max-width: 980px;
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
  border-bottom: 1px solid var(--border);
}

.tab {
  padding: 8px 14px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--text-muted);
  font: inherit;
  cursor: pointer;
}

.tab:hover {
  color: var(--text);
  background: var(--hover);
}

.tab.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}
</style>
