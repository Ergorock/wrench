<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import type { Layout, Layouts, OpenItem, OpenWindows, Restore } from './types'

const PREFIX = 'tools.window_layout.'

const { t, locale } = useI18n()
const tool = useTool('window_layout')

const open = ref<OpenItem[]>([])
const layouts = ref<Layout[]>([])
const newName = ref('')
const busy = ref(false)
const confirmDelete = ref<string | null>(null)
const restoreResult = ref<{ name: string; result: Restore } | null>(null)

const missingList = computed(() => (restoreResult.value?.result.missing ?? []).map((m) => `${m.exe}`).join(', '))

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(locale.value, { dateStyle: 'short', timeStyle: 'short' })
}

async function refresh(): Promise<void> {
  try {
    open.value = (await tool.call<OpenWindows>('list_windows')).windows
  } catch {
    // useTool has already shown the error toast.
  }
}

async function loadLayouts(): Promise<void> {
  try {
    layouts.value = (await tool.call<Layouts>('get_layouts')).layouts
  } catch {
    // useTool has already shown the error toast.
  }
}

async function save(): Promise<void> {
  busy.value = true
  try {
    layouts.value = (await tool.call<Layouts>('save_layout', { name: newName.value })).layouts
    newName.value = ''
    restoreResult.value = null
  } catch {
    // useTool has already shown the error toast.
  } finally {
    busy.value = false
  }
}

async function restore(layout: Layout): Promise<void> {
  busy.value = true
  try {
    const result = await tool.call<Restore>('restore_layout', { layout_id: layout.id })
    restoreResult.value = { name: layout.name, result }
    await refresh()
  } catch {
    // useTool has already shown the error toast.
  } finally {
    busy.value = false
  }
}

async function remove(id: string): Promise<void> {
  try {
    layouts.value = (await tool.call<Layouts>('delete_layout', { layout_id: id })).layouts
  } catch {
    // useTool has already shown the error toast.
  } finally {
    confirmDelete.value = null
  }
}

onMounted(() => {
  void refresh()
  void loadLayouts()
})
</script>

<template>
  <div class="layout">
    <p class="hint">{{ t(`${PREFIX}note`) }}</p>

    <section class="panel">
      <div class="head">
        <h2>{{ t(`${PREFIX}openTitle`) }}</h2>
        <button type="button" class="button" @click="refresh">{{ t(`${PREFIX}refresh`) }}</button>
      </div>
      <p v-if="open.length === 0" class="hint">{{ t(`${PREFIX}noOpen`) }}</p>
      <ul v-else class="list small">
        <li v-for="(w, i) in open" :key="`${w.exe}-${i}`">
          <code>{{ w.exe }}</code> <span class="title">{{ w.title }}</span>
        </li>
      </ul>
    </section>

    <section class="panel">
      <h2>{{ t(`${PREFIX}saveTitle`) }}</h2>
      <form class="line" @submit.prevent="save">
        <label class="field">
          <span>{{ t(`${PREFIX}layoutName`) }}</span>
          <input v-model="newName" maxlength="60" />
        </label>
        <button type="submit" class="button primary" :disabled="busy || newName.trim() === ''">
          {{ t(`${PREFIX}save`) }}
        </button>
      </form>
    </section>

    <section class="panel">
      <h2>{{ t(`${PREFIX}layoutsTitle`) }}</h2>
      <p v-if="layouts.length === 0" class="hint">{{ t(`${PREFIX}noLayouts`) }}</p>
      <ul v-else class="list">
        <li v-for="l in layouts" :key="l.id" :data-layout="l.name" class="item">
          <div class="info">
            <strong>{{ l.name }}</strong>
            <small class="hint">
              {{ t(`${PREFIX}savedAt`, { date: formatDate(l.saved_at), count: l.windows.length }) }}
            </small>
          </div>
          <div class="actions">
            <button type="button" class="button primary" :disabled="busy" @click="restore(l)">
              {{ t(`${PREFIX}restore`) }}
            </button>
            <template v-if="confirmDelete === l.id">
              <button type="button" class="button danger" @click="remove(l.id)">
                {{ t(`${PREFIX}confirmDelete`) }}
              </button>
              <button type="button" class="button" @click="confirmDelete = null">
                {{ t(`${PREFIX}cancel`) }}
              </button>
            </template>
            <button v-else type="button" class="button" @click="confirmDelete = l.id">
              {{ t(`${PREFIX}delete`) }}
            </button>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="restoreResult" class="panel result" role="status">
      <p>
        <strong>{{ restoreResult.name }}</strong> :
        {{ t(`${PREFIX}restored`, { count: restoreResult.result.restored }) }}
      </p>
      <p v-if="restoreResult.result.missing.length > 0" class="hint">
        {{ t(`${PREFIX}missing`, { list: missingList }) }}
      </p>
    </section>
  </div>
</template>

<style scoped>
.layout {
  max-width: 820px;
}
.hint {
  margin: 0 0 12px;
  color: var(--text-muted);
  font-size: 13px;
}
.panel {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.panel h2 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.head h2 {
  margin: 0;
}
.line {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  font-size: 13px;
  color: var(--text-muted);
}
input {
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.button {
  padding: 7px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--active);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.button.primary {
  background: var(--accent);
  color: var(--accent-text);
  border-color: transparent;
}
.button.danger {
  border-color: var(--danger);
  color: var(--danger);
}
.button:disabled {
  opacity: 0.5;
  cursor: default;
}
.button:focus-visible,
input:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.list.small {
  max-height: 220px;
  overflow: auto;
  font-size: 13px;
}
.list.small li {
  padding: 5px 10px;
}
.list.small li + li {
  border-top: 1px solid var(--border);
}
.title {
  color: var(--text-muted);
  overflow-wrap: anywhere;
}
.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
}
.item + .item {
  border-top: 1px solid var(--border);
}
.info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.result p {
  margin: 0 0 6px;
}
.result p:last-child {
  margin-bottom: 0;
}
</style>
