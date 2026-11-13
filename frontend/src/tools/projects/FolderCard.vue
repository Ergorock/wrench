<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Folder, FolderOpen } from '@lucide/vue'
import { useTool } from '../../bridge/useTool'
import type { FolderEntry } from './types'

const props = defineProps<{ folder: FolderEntry }>()
const emit = defineEmits<{ open: [] }>()

const { t } = useI18n()
const tool = useTool('projects')

async function openInExplorer(): Promise<void> {
  try {
    await tool.call('open_folder', { path: props.folder.path })
  } catch {
    // useTool has already shown the error toast.
  }
}
</script>

<template>
  <div class="folder-wrap">
    <button type="button" class="folder-card" :data-folder="folder.rel_path" @click="emit('open')">
      <Folder :size="20" aria-hidden="true" />
      <span class="name">{{ folder.name }}</span>
      <span class="count">{{ t('tools.projects.folder.count', { n: folder.project_count }, folder.project_count) }}</span>
    </button>
    <button
      type="button"
      class="open-folder"
      :title="t('tools.projects.folder.openTitle')"
      :aria-label="t('tools.projects.folder.open', { name: folder.name })"
      @click.stop="openInExplorer"
    >
      <FolderOpen :size="16" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
.folder-wrap {
  position: relative;
  display: flex;
}
.folder-card {
  flex: 1;
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
.open-folder {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
}
.open-folder:hover {
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
