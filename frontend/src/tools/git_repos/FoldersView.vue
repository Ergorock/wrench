<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderPlus, TriangleAlert } from '@lucide/vue'
import { pickFolder } from '../../bridge/client'
import { toastError } from '../../shell/toasts'
import type { RepoConfig } from './types'

const PREFIX = 'tools.git_repos.'
const DEPTHS = [1, 2, 3, 4, 5, 6]

const props = defineProps<{ config: RepoConfig }>()
const emit = defineEmits<{ save: [roots: string[], maxDepth: number]; cancel: [] }>()

const { t } = useI18n()
const roots = ref<string[]>([...props.config.roots])
const depth = ref(props.config.max_depth)

async function add(): Promise<void> {
  let folder: string | null
  try {
    folder = await pickFolder(roots.value.at(-1))
  } catch (err) {
    // pickFolder is a shell call, not a tool action: nothing has shown this error yet.
    toastError(err)
    return
  }
  if (folder !== null && !roots.value.some((r) => r.toLowerCase() === folder.toLowerCase())) {
    roots.value = [...roots.value, folder]
  }
}

function remove(root: string): void {
  roots.value = roots.value.filter((r) => r !== root)
}
</script>

<template>
  <div class="folders">
    <h2>{{ t(`${PREFIX}folders.title`) }}</h2>
    <p class="hint">{{ t(`${PREFIX}folders.hint`) }}</p>
    <ul v-if="roots.length > 0" class="roots">
      <li v-for="root in roots" :key="root">
        <span class="path">{{ root }}</span>
        <span v-if="config.missing_roots.includes(root)" class="missing">
          <TriangleAlert :size="14" aria-hidden="true" />
          {{ t(`${PREFIX}folders.missing`) }}
        </span>
        <button type="button" @click="remove(root)">{{ t(`${PREFIX}folders.remove`) }}</button>
      </li>
    </ul>
    <p v-else class="hint">{{ t(`${PREFIX}folders.none`) }}</p>
    <button type="button" class="add" @click="add">
      <FolderPlus :size="16" aria-hidden="true" />
      {{ t(`${PREFIX}folders.add`) }}
    </button>
    <label class="depth">
      {{ t(`${PREFIX}folders.depth`) }}
      <select v-model.number="depth">
        <option v-for="d in DEPTHS" :key="d" :value="d">{{ d }}</option>
      </select>
    </label>
    <div class="buttons">
      <button type="button" @click="emit('cancel')">{{ t(`${PREFIX}folders.cancel`) }}</button>
      <button type="button" class="primary" @click="emit('save', roots, depth)">
        {{ t(`${PREFIX}folders.save`) }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.folders {
  max-width: 720px;
}
h2 {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 600;
}
.hint {
  margin: 0 0 12px;
  color: var(--text-muted);
}
.roots {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.roots li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.roots li:last-child {
  border-bottom: none;
}
.path {
  flex: 1;
  overflow-wrap: anywhere;
}
.missing {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--danger);
  font-size: 12px;
}
.depth {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 0;
}
select,
button {
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
button:hover {
  background: var(--hover);
}
.add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.buttons {
  display: flex;
  gap: 8px;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
</style>
