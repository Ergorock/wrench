<script setup lang="ts">
import { BarChart3, Download, List } from '@lucide/vue'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { pushToast } from '../../shell/toasts'
import JobPanel from './JobPanel.vue'
import CsvButton from './CsvButton.vue'
import SessionBar from './SessionBar.vue'
import { filterRows, toggleAll } from './logic'
import type { Workspace, WsResult } from './types'
import { useM3 } from './useM3'

const PREFIX = 'tools.m3.widgets.'
const { t } = useI18n()
const m3 = useM3()

type Kind = 'workspaces' | 'insights'
interface Item extends Workspace {
  kind: Kind
}

const KINDS: Kind[] = ['workspaces', 'insights']

const token = ref('')
const query = ref('')
const items = ref<Item[] | null>(null)
const selected = ref<Set<string>>(new Set())
const result = ref<WsResult | null>(null)

const busy = computed(() => m3.state.value?.job.running === true)
const connected = computed(() => m3.state.value?.connected.workspaces === true)
const rows = computed(() => filterRows(items.value ?? [], query.value, (i) => [i.title, i.owner]))

async function useToken(): Promise<void> {
  try {
    await m3.call('set_token', { token: token.value })
    token.value = ''
  } catch {
    // useTool has already shown the error toast.
  }
}

async function list(): Promise<void> {
  try {
    const found: Item[] = []
    for (const kind of KINDS) {
      const part = await m3.call<Workspace[]>('ws_list', { kind })
      found.push(...part.map((w) => ({ ...w, kind })))
    }
    items.value = found
    selected.value = new Set([...selected.value].filter((id) => found.some((i) => i.id === id)))
  } catch {
    // useTool has already shown the error toast.
  }
}

const allSelected = computed(
  () => rows.value.length > 0 && rows.value.every((i) => selected.value.has(i.id)),
)
const someSelected = computed(
  () => !allSelected.value && rows.value.some((i) => selected.value.has(i.id)),
)
const listCsv = computed(() =>
  rows.value.map((i) => [i.title, t(`${PREFIX}kinds.${i.kind}`), i.owner, i.changed]),
)

function toggleEvery(): void {
  selected.value = toggleAll(
    selected.value,
    rows.value.map((i) => i.id),
  )
}

function toggle(id: string): void {
  const next = new Set(selected.value)
  if (!next.delete(id)) next.add(id)
  selected.value = next
}

async function analyze(): Promise<void> {
  try {
    await m3.call('ws_analyze', { ids: [...selected.value] })
  } catch {
    // useTool has already shown the error toast.
  }
}

async function exportCsv(): Promise<void> {
  try {
    const path = await m3.call<string>('ws_export_csv')
    pushToast(t(`${PREFIX}exported`, { path }), 'info')
  } catch {
    // useTool has already shown the error toast.
  }
}

m3.onJobEnd(async (job) => {
  if (job.error) return
  if (job.kind === 'login_workspaces') void list()
  if (job.kind === 'ws_analyze') result.value = await m3.call<WsResult>('ws_result')
})
</script>

<template>
  <div class="m3-panel">
    <SessionBar target="workspaces" />
    <details class="token">
      <summary>{{ t(`${PREFIX}tokenTitle`) }}</summary>
      <div class="m3-row">
        <input v-model="token" type="password" autocomplete="off" :placeholder="t(`${PREFIX}tokenPlaceholder`)" />
        <button type="button" :disabled="token.trim() === ''" @click="useToken">
          {{ t(`${PREFIX}tokenUse`) }}
        </button>
      </div>
      <p class="m3-muted">{{ t(`${PREFIX}tokenHelp`) }}</p>
    </details>

    <div class="m3-row">
      <button type="button" :disabled="busy || !connected" @click="list">
        <List :size="15" class="m3-icon" />
        {{ t(`${PREFIX}list`) }}
      </button>
      <input v-model="query" type="text" :placeholder="t(`${PREFIX}filter`)" :disabled="items === null" />
      <button
        type="button"
        class="primary"
        :disabled="busy || !connected || selected.size === 0"
        @click="analyze"
      >
        <BarChart3 :size="15" class="m3-icon" />
        {{ t(`${PREFIX}analyze`, { count: selected.size }) }}
      </button>
      <CsvButton
        name="workspaces"
        :header="[
          t(`${PREFIX}columns.title`),
          t(`${PREFIX}columns.kind`),
          t(`${PREFIX}columns.owner`),
          t(`${PREFIX}columns.changed`),
        ]"
        :rows="listCsv"
      />
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
            <th>{{ t(`${PREFIX}columns.title`) }}</th>
            <th>{{ t(`${PREFIX}columns.kind`) }}</th>
            <th>{{ t(`${PREFIX}columns.owner`) }}</th>
            <th>{{ t(`${PREFIX}columns.changed`) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in rows" :key="i.id">
            <td><input type="checkbox" :checked="selected.has(i.id)" @change="toggle(i.id)" /></td>
            <td>{{ i.title }}</td>
            <td>{{ t(`${PREFIX}kinds.${i.kind}`) }}</td>
            <td>{{ i.owner }}</td>
            <td>{{ i.changed }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <JobPanel :kinds="['ws_analyze']" />

    <template v-if="result !== null">
      <div class="m3-row">
        <strong>{{ t(`${PREFIX}results`, { count: result.totals.length }) }}</strong>
        <button type="button" :disabled="result.rows.length === 0" @click="exportCsv">
          <Download :size="15" class="m3-icon" />
          {{ t(`${PREFIX}exportCsv`) }}
        </button>
      </div>
      <div class="m3-table-wrap">
        <table class="m3-table">
          <thead>
            <tr>
              <th>{{ t(`${PREFIX}columns.widgetId`) }}</th>
              <th>{{ t(`${PREFIX}columns.label`) }}</th>
              <th class="num">{{ t(`${PREFIX}columns.count`) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in result.totals" :key="w.widget_id">
              <td>{{ w.widget_id }}</td>
              <td>{{ w.label }}</td>
              <td class="num">{{ w.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.token {
  color: var(--text-muted);
  font-size: 12px;
}

.token summary {
  cursor: pointer;
}

.token .m3-row {
  margin-top: 8px;
}

.token input {
  flex: 1;
  max-width: 420px;
}
</style>
