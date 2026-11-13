<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Folder } from '@lucide/vue'
import type { FolderEntry } from './types'

defineProps<{ folder: FolderEntry }>()
const emit = defineEmits<{ open: [] }>()

const { t } = useI18n()
</script>

<template>
  <button type="button" class="folder-card" :data-folder="folder.rel_path" @click="emit('open')">
    <Folder :size="20" aria-hidden="true" />
    <span class="name">{{ folder.name }}</span>
    <span class="count">{{ t('tools.projects.folder.count', { n: folder.project_count }, folder.project_count) }}</span>
  </button>
</template>

<style scoped>
.folder-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.folder-card:hover {
  background: var(--hover);
}
.name {
  font-weight: 600;
  overflow-wrap: anywhere;
}
.count {
  color: var(--text-muted);
  font-size: 12px;
}
</style>
