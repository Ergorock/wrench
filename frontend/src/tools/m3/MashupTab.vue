<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SessionBar from './SessionBar.vue'
import { filterRows, sortRows } from './logic'
import type { Mashup } from './types'
import { useM3 } from './useM3'

const PREFIX = 'tools.m3.mashup.'
const { t } = useI18n()
const m3 = useM3()

type Column = keyof Mashup
const COLUMNS: Column[] = [
  'name',
  'description',
  'category',
  'visibility',
  'created_by',
  'changed_by',
  'change_date',
]

const apps = ref<Mashup[] | null>(null)
const query = ref('')
const sortBy = ref<Column>('name')
const desc = ref(false)

const rows = computed(() =>
  sortRows(
    filterRows(apps.value ?? [], query.value, (a) => [a.name, a.description]),
    (a) => a[sortBy.value],
    desc.value,
  ),
)
const busy = computed(() => m3.state.value?.job.running === true)
const connected = computed(() => m3.state.value?.connected.mashup === true)

function sort(column: Column): void {
  if (sortBy.value === column) desc.value = !desc.value
  else {
    sortBy.value = column
    desc.value = false
  }
}

async function load(): Promise<void> {
  try {
    apps.value = await m3.call<Mashup[]>('mashup_list')
  } catch {
    // useTool has already shown the error toast; an expired session shows as disconnected.
  }
}

// A successful login loads the list straight away.
m3.onJobEnd((job) => {
  if (job.kind === 'login_mashup' && !job.error) void load()
})
</script>

<template>
  <div class="m3-panel">
    <SessionBar target="mashup" />
    <div class="m3-row">
      <button type="button" :disabled="busy || !connected" @click="load">
        {{ t(`${PREFIX}refresh`) }}
      </button>
      <input v-model="query" type="text" :placeholder="t(`${PREFIX}filter`)" :disabled="apps === null" />
      <span v-if="apps !== null" class="m3-muted">
        {{ t(`${PREFIX}count`, { count: rows.length, total: apps.length }) }}
      </span>
    </div>
    <div v-if="apps !== null" class="m3-table-wrap">
      <table class="m3-table">
        <thead>
          <tr>
            <th v-for="c in COLUMNS" :key="c" class="sortable" @click="sort(c)">
              {{ t(`${PREFIX}columns.${c}`) }}{{ sortBy === c ? (desc ? ' ▼' : ' ▲') : '' }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in rows" :key="a.name">
            <td v-for="c in COLUMNS" :key="c">{{ a[c] }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
