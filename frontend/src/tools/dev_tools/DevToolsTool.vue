<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ColorTab from './ColorTab.vue'
import EncodeTab from './EncodeTab.vue'
import FormatTab from './FormatTab.vue'

const PREFIX = 'tools.dev_tools.'
const { t } = useI18n()

const TABS = ['encode', 'color', 'json', 'xml'] as const
type TabId = (typeof TABS)[number]

// Every tab stays mounted (v-show), so switching tabs keeps what was typed.
const current = ref<TabId>('encode')
</script>

<template>
  <div class="dev-tools">
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

    <EncodeTab v-show="current === 'encode'" />
    <ColorTab v-show="current === 'color'" />
    <FormatTab v-show="current === 'json'" kind="json" />
    <FormatTab v-show="current === 'xml'" kind="xml" />
  </div>
</template>

<style scoped>
.dev-tools {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 880px;
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
