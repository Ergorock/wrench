<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import { pickFolder } from '../../bridge/client'
import type { Applied, Candidate, Filters, Scan } from './types'

const PREFIX = 'tools.downloads_cleaner.'
const MB = 1024 * 1024

const { t, te, locale } = useI18n()
const tool = useTool('downloads_cleaner')

// ---- Filters --------------------------------------------------------------

const folder = ref('')
const extensionsText = ref('')
const minAgeDays = ref(0)
const minSizeMb = ref(0)

function currentFilters(): Filters {
  return {
    folder: folder.value,
    extensions: extensionsText.value
      .split(',')
      .map((e) => e.trim())
      .filter((e) => e !== ''),
    min_age_days: Math.max(0, Math.floor(minAgeDays.value || 0)),
    min_size_mb: Math.max(0, minSizeMb.value || 0),
  }
}

async function chooseFolder(): Promise<void> {
  const picked = await pickFolder(folder.value || undefined)
  if (picked !== null) folder.value = picked
}

// ---- Scan and selection ---------------------------------------------------

const scan = ref<Scan | null>(null)
const selected = ref<Set<string>>(new Set())
const confirming = ref(false)
const summary = ref<Applied | null>(null)
const busy = ref(false)

const formatter = computed(() => new Intl.NumberFormat(locale.value, { maximumFractionDigits: 1 }))
const formatSize = (bytes: number): string => {
  if (bytes >= MB) return `${formatter.value.format(bytes / MB)} Mo`
  return `${formatter.value.format(bytes / 1024)} Ko`
}

const selectedFiles = computed<Candidate[]>(
  () => (scan.value?.files ?? []).filter((f) => selected.value.has(f.name)),
)
const selectedSize = computed(() => selectedFiles.value.reduce((sum, f) => sum + f.size, 0))

function fillSelection(): void {
  selected.value = new Set((scan.value?.files ?? []).map((f) => f.name))
}

function toggle(name: string): void {
  const next = new Set(selected.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  selected.value = next
  confirming.value = false
}

async function runScan(): Promise<void> {
  if (!folder.value) return
  busy.value = true
  summary.value = null
  confirming.value = false
  try {
    scan.value = await tool.call<Scan>('scan', { filters: currentFilters() })
    fillSelection()
  } catch {
    // useTool has already shown the error toast.
  } finally {
    busy.value = false
  }
}

async function sendToTrash(): Promise<void> {
  const names = selectedFiles.value.map((f) => f.name)
  if (names.length === 0) return
  busy.value = true
  try {
    const applied = await tool.call<Applied>('send_to_trash', {
      filters: currentFilters(),
      names,
    })
    summary.value = applied
    // Only the files that are gone leave the list. The rest stay selected as they were, so
    // nothing is re-selected by surprise before the next confirmation.
    const removed = new Set(applied.removed)
    if (scan.value) {
      const files = scan.value.files.filter((f) => !removed.has(f.name))
      scan.value = { ...scan.value, files, total_size: files.reduce((sum, f) => sum + f.size, 0) }
    }
    selected.value = new Set([...selected.value].filter((name) => !removed.has(name)))
  } catch {
    // useTool has already shown the error toast.
  } finally {
    confirming.value = false
    busy.value = false
  }
}

function reasonText(reason: string): string {
  const key = `${PREFIX}reasons.${reason}`
  return te(key) ? t(key) : reason
}

function formatDate(day: string): string {
  return new Date(`${day}T00:00:00`).toLocaleDateString(locale.value)
}

onMounted(async () => {
  try {
    const saved = await tool.call<Filters>('get_settings')
    folder.value = saved.folder
    extensionsText.value = saved.extensions.join(', ')
    minAgeDays.value = saved.min_age_days
    minSizeMb.value = saved.min_size_mb
  } catch {
    // useTool has already shown the error toast.
  }
})
</script>

<template>
  <div class="cleaner">
    <section class="panel">
      <div class="folder">
        <span class="path" :title="folder">{{ folder || t(`${PREFIX}noFolder`) }}</span>
        <button type="button" class="button" @click="chooseFolder">
          {{ t(`${PREFIX}chooseFolder`) }}
        </button>
      </div>

      <div class="line">
        <label class="field">
          <span>{{ t(`${PREFIX}extensions`) }}</span>
          <input v-model="extensionsText" :placeholder="t(`${PREFIX}extensionsPlaceholder`)" />
        </label>
        <label class="field narrow">
          <span>{{ t(`${PREFIX}minAge`) }}</span>
          <input v-model.number="minAgeDays" type="number" min="0" step="1" />
        </label>
        <label class="field narrow">
          <span>{{ t(`${PREFIX}minSize`) }}</span>
          <input v-model.number="minSizeMb" type="number" min="0" step="any" />
        </label>
      </div>

      <button type="button" class="button primary" :disabled="!folder || busy" @click="runScan">
        {{ t(`${PREFIX}scan`) }}
      </button>
    </section>

    <p v-if="summary" class="summary" role="status">
      {{ t(`${PREFIX}removedCount`, { count: summary.removed.length }) }}
      <span class="hint">{{ t(`${PREFIX}inBin`) }}</span>
    </p>
    <ul v-if="summary && summary.failed.length > 0" class="failures">
      <li v-for="f in summary.failed" :key="f.name">
        {{ f.name }} : {{ reasonText(f.reason) }}
      </li>
    </ul>

    <section v-if="scan" class="panel results">
      <p class="hint">
        {{ t(`${PREFIX}found`, { count: scan.files.length, size: formatSize(scan.total_size) }) }}
      </p>

      <p v-if="scan.files.length === 0" class="hint">{{ t(`${PREFIX}noFiles`) }}</p>

      <template v-else>
        <div class="line actions">
          <button type="button" class="button" @click="fillSelection">
            {{ t(`${PREFIX}selectAll`) }}
          </button>
          <button type="button" class="button" @click="selected = new Set()">
            {{ t(`${PREFIX}selectNone`) }}
          </button>
        </div>

        <ul class="files">
          <li v-for="f in scan.files" :key="f.name" :data-file="f.name" class="file">
            <label>
              <input type="checkbox" :checked="selected.has(f.name)" @change="toggle(f.name)" />
              <span class="name">{{ f.name }}</span>
            </label>
            <span class="meta">{{ formatSize(f.size) }} · {{ formatDate(f.modified) }}</span>
          </li>
        </ul>

        <div class="trash">
          <p v-if="!confirming" class="hint">
            {{ t(`${PREFIX}selectedCount`, { count: selectedFiles.length, size: formatSize(selectedSize) }) }}
          </p>
          <p v-else class="warning" role="alert">
            {{ t(`${PREFIX}confirmText`, { count: selectedFiles.length, size: formatSize(selectedSize) }) }}
          </p>
          <div class="line">
            <button
              v-if="!confirming"
              type="button"
              class="button danger"
              :disabled="selectedFiles.length === 0 || busy"
              @click="confirming = true"
            >
              {{ t(`${PREFIX}sendToTrash`) }}
            </button>
            <template v-else>
              <button type="button" class="button danger" :disabled="busy" @click="sendToTrash">
                {{ t(`${PREFIX}confirm`) }}
              </button>
              <button type="button" class="button" @click="confirming = false">
                {{ t(`${PREFIX}cancel`) }}
              </button>
            </template>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.cleaner {
  max-width: 820px;
}
.panel {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.folder {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono, monospace);
  font-size: 13px;
}
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 140px;
  font-size: 13px;
  color: var(--text-muted);
}
.field.narrow {
  flex: 0 0 110px;
  min-width: 0;
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
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}
.summary {
  margin: 0 0 8px;
  font-weight: 600;
}
.failures {
  margin: 0 0 16px;
  color: var(--danger);
  font-size: 13px;
}
.results .actions {
  margin-bottom: 8px;
}
.files {
  margin: 0 0 16px;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  max-height: 360px;
  overflow: auto;
}
.file {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 10px;
}
.file + .file {
  border-top: 1px solid var(--border);
}
.file label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.name {
  overflow-wrap: anywhere;
}
.meta {
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: 13px;
}
.warning {
  margin: 0 0 10px;
  color: var(--danger);
  font-weight: 600;
}
</style>
