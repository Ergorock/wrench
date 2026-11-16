<script setup lang="ts">
import { FileDown, List, ListPlus } from '@lucide/vue'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CsvButton from './CsvButton.vue'
import JobPanel from './JobPanel.vue'
import SessionBar from './SessionBar.vue'
import { countEdas, filterRows, toggleAll } from './logic'
import type { EdaItem } from './types'
import { useM3 } from './useM3'

const PREFIX = 'tools.m3.eda.'
const MAX_COLUMNS = 6
const { t } = useI18n()
const m3 = useM3()

const edas = ref('')
const count = computed(() => countEdas(edas.value))
const busy = computed(() => m3.state.value?.job.running === true)
const connected = computed(() => m3.state.value?.connected.eda === true)

// ---- Server list ------------------------------------------------------------

const items = ref<EdaItem[] | null>(null)
const query = ref('')
const selected = ref<Set<string>>(new Set())

const rows = computed(() =>
  filterRows(items.value ?? [], query.value, (i) => Object.values(i.fields)),
)
// The server's own field names, in order of first appearance, capped to keep the table readable.
const columns = computed(() => {
  const names = new Set<string>()
  for (const item of items.value ?? []) {
    for (const key of Object.keys(item.fields)) names.add(key)
    if (names.size >= MAX_COLUMNS) break
  }
  return [...names].slice(0, MAX_COLUMNS)
})
const allSelected = computed(
  () => rows.value.length > 0 && rows.value.every((i) => selected.value.has(i.id)),
)
const someSelected = computed(
  () => !allSelected.value && rows.value.some((i) => selected.value.has(i.id)),
)
const csvRows = computed(() => rows.value.map((i) => columns.value.map((c) => i.fields[c] ?? '')))

async function list(): Promise<void> {
  try {
    items.value = await m3.call<EdaItem[]>('eda_list')
    selected.value = new Set()
  } catch {
    // useTool has already shown the error toast.
  }
}

function toggle(id: string): void {
  const next = new Set(selected.value)
  if (!next.delete(id)) next.add(id)
  selected.value = next
}

function toggleEvery(): void {
  selected.value = toggleAll(
    selected.value,
    rows.value.map((i) => i.id),
  )
}

function addSelected(): void {
  const known = new Set(edas.value.split(/\r?\n/).map((l) => l.split(/[;\t,]/)[0].trim()))
  const added = (items.value ?? []).filter((i) => selected.value.has(i.id) && !known.has(i.id))
  const base = edas.value.trimEnd()
  edas.value = [base, ...added.map((i) => i.id)].filter((l) => l !== '').join('\n')
}

// A successful login lists the EDAs straight away.
m3.onJobEnd((job) => {
  if (job.kind === 'login_eda' && !job.error) void list()
})

// ---- Export -----------------------------------------------------------------

async function save(): Promise<void> {
  try {
    await m3.saveConfig()
  } catch {
    // useTool has already shown the error toast.
  }
}

async function run(): Promise<void> {
  try {
    await m3.call('eda_export', { edas: edas.value })
  } catch {
    // useTool has already shown the error toast.
  }
}
</script>

<template>
  <div class="m3-panel">
    <div class="m3-row">
      <label class="m3-field url">
        {{ t(`${PREFIX}baseUrl`) }}
        <input v-model="m3.config.value.eda_base_url" type="text" spellcheck="false" @change="save" />
      </label>
      <label class="m3-field short">
        {{ t(`${PREFIX}company`) }}
        <input v-model="m3.config.value.company" type="text" @change="save" />
      </label>
      <label class="m3-field short">
        {{ t(`${PREFIX}division`) }}
        <input v-model="m3.config.value.division" type="text" @change="save" />
      </label>
      <label class="m3-field short">
        {{ t(`${PREFIX}language`) }}
        <input v-model="m3.config.value.language" type="text" @change="save" />
      </label>
    </div>

    <SessionBar target="eda" />

    <div class="m3-row">
      <button type="button" :disabled="busy || !connected" @click="list">
        <List :size="15" class="m3-icon" />
        {{ t(`${PREFIX}listEdas`) }}
      </button>
      <input v-model="query" type="text" :placeholder="t(`${PREFIX}filter`)" :disabled="items === null" />
      <button type="button" :disabled="selected.size === 0" @click="addSelected">
        <ListPlus :size="15" class="m3-icon" />
        {{ t(`${PREFIX}addSelected`, { count: selected.size }) }}
      </button>
      <CsvButton name="eda_list" :header="columns" :rows="csvRows" />
      <span v-if="items !== null" class="m3-muted">
        {{ t(`${PREFIX}count`, { count: rows.length, total: items.length }) }}
      </span>
    </div>

    <div v-if="items !== null" class="m3-table-wrap">
      <table class="m3-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                :checked="allSelected"
                :indeterminate.prop="someSelected"
                :aria-label="t(`${PREFIX}selectAll`)"
                @change="toggleEvery"
              />
            </th>
            <th v-for="c in columns" :key="c">{{ c }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in rows" :key="i.id">
            <td><input type="checkbox" :checked="selected.has(i.id)" @change="toggle(i.id)" /></td>
            <td v-for="c in columns" :key="c" class="nowrap">{{ i.fields[c] ?? '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <label class="m3-field">
      {{ t(`${PREFIX}list`) }}
      <textarea v-model="edas" rows="6" spellcheck="false" :placeholder="t(`${PREFIX}placeholder`)" />
    </label>

    <div class="m3-row">
      <button type="button" class="primary" :disabled="busy || !connected || count === 0" @click="run">
        <FileDown :size="15" class="m3-icon" />
        {{ t(`${PREFIX}export`, { count }) }}
      </button>
      <span class="m3-muted">{{ t(`${PREFIX}target`, { dir: m3.config.value.output_dir }) }}</span>
    </div>

    <JobPanel :kinds="['eda_export']" />
  </div>
</template>

<style scoped>
.url {
  flex: 1;
  min-width: 220px;
}

.short input {
  width: 80px;
}
</style>
