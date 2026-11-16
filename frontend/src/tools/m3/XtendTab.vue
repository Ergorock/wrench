<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import JobPanel from './JobPanel.vue'
import SessionBar from './SessionBar.vue'
import { filterRows } from './logic'
import type { XtendHit, XtendSource } from './types'
import { useM3 } from './useM3'

const PREFIX = 'tools.m3.xtend.'
const { t } = useI18n()
const m3 = useM3()

const sources = ref<XtendSource[] | null>(null)
const query = ref('')
const selected = ref<Set<string>>(new Set())

const busy = computed(() => m3.state.value?.job.running === true)
const connected = computed(() => m3.state.value?.connected.xtend === true)
const rows = computed(() =>
  filterRows(sources.value ?? [], query.value, (s) => [s.program, s.name, s.description]),
)

async function list(): Promise<void> {
  try {
    sources.value = await m3.call<XtendSource[]>('xtend_list')
    selected.value = new Set()
  } catch {
    // useTool has already shown the error toast.
  }
}

function toggle(uuid: string): void {
  const next = new Set(selected.value)
  if (!next.delete(uuid)) next.add(uuid)
  selected.value = next
}

async function fetchCode(all: boolean): Promise<void> {
  try {
    await m3.call('xtend_fetch', { uuids: all ? [] : [...selected.value] })
  } catch {
    // useTool has already shown the error toast.
  }
}

// ---- Local search -----------------------------------------------------------

const search = ref('')
const regex = ref(false)
const caseSensitive = ref(false)
const kinds = ref<Set<string>>(new Set(['batch', 'transaction']))
const hits = ref<XtendHit[] | null>(null)
const viewing = ref<{ hit: XtendHit; lines: string[] } | null>(null)
const lineEls = ref<HTMLElement[]>([])

function toggleKind(kind: string): void {
  const next = new Set(kinds.value)
  if (!next.delete(kind)) next.add(kind)
  kinds.value = next
}

async function runSearch(): Promise<void> {
  try {
    hits.value = await m3.call<XtendHit[]>('xtend_search', {
      query: search.value,
      regex: regex.value,
      case_sensitive: caseSensitive.value,
      kinds: [...kinds.value],
    })
    viewing.value = null
  } catch {
    // useTool has already shown the error toast.
  }
}

async function open(hit: XtendHit): Promise<void> {
  try {
    const code = await m3.call<string>('xtend_read', { file: hit.file })
    viewing.value = { hit, lines: code.split(/\r?\n/) }
    await nextTick()
    lineEls.value[hit.line - 1]?.scrollIntoView({ block: 'center' })
  } catch {
    // useTool has already shown the error toast.
  }
}

// A successful login lists the programs straight away.
m3.onJobEnd((job) => {
  if (job.kind === 'login_xtend' && !job.error) void list()
})
</script>

<template>
  <div class="m3-panel">
    <SessionBar target="xtend" />

    <div class="m3-row">
      <button type="button" :disabled="busy || !connected" @click="list">{{ t(`${PREFIX}list`) }}</button>
      <input v-model="query" type="text" :placeholder="t(`${PREFIX}filter`)" :disabled="sources === null" />
      <button type="button" :disabled="busy || !connected || selected.size === 0" @click="fetchCode(false)">
        {{ t(`${PREFIX}fetchSelected`, { count: selected.size }) }}
      </button>
      <button type="button" class="primary" :disabled="busy || !connected || sources === null" @click="fetchCode(true)">
        {{ t(`${PREFIX}fetchAll`) }}
      </button>
    </div>

    <div v-if="sources !== null" class="m3-table-wrap">
      <table class="m3-table">
        <thead>
          <tr>
            <th></th>
            <th>{{ t(`${PREFIX}columns.program`) }}</th>
            <th>{{ t(`${PREFIX}columns.kind`) }}</th>
            <th>{{ t(`${PREFIX}columns.name`) }}</th>
            <th>{{ t(`${PREFIX}columns.description`) }}</th>
            <th>{{ t(`${PREFIX}columns.modifiedBy`) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in rows" :key="s.uuid">
            <td><input type="checkbox" :checked="selected.has(s.uuid)" @change="toggle(s.uuid)" /></td>
            <td>{{ s.program }}</td>
            <td>{{ t(`${PREFIX}kinds.${s.kind}`) }}</td>
            <td>{{ s.name }}</td>
            <td>{{ s.description }}</td>
            <td>{{ s.modified_by }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <JobPanel :kinds="['xtend_fetch']" />

    <h3 class="title">{{ t(`${PREFIX}searchTitle`) }}</h3>
    <p class="m3-muted">{{ t(`${PREFIX}searchHelp`, { dir: m3.config.value.output_dir }) }}</p>
    <form class="m3-row" @submit.prevent="runSearch">
      <input v-model="search" type="text" class="query" spellcheck="false" :placeholder="t(`${PREFIX}searchPlaceholder`)" />
      <label class="m3-muted"><input v-model="regex" type="checkbox" /> {{ t(`${PREFIX}regex`) }}</label>
      <label class="m3-muted">
        <input v-model="caseSensitive" type="checkbox" /> {{ t(`${PREFIX}caseSensitive`) }}
      </label>
      <label v-for="k in ['batch', 'transaction']" :key="k" class="m3-muted">
        <input type="checkbox" :checked="kinds.has(k)" @change="toggleKind(k)" /> {{ t(`${PREFIX}kinds.${k}`) }}
      </label>
      <button type="submit" class="primary" :disabled="search.trim() === ''">{{ t(`${PREFIX}search`) }}</button>
    </form>

    <template v-if="hits !== null">
      <p class="m3-muted">{{ t(`${PREFIX}hits`, { count: hits.length }) }}</p>
      <div v-if="hits.length > 0" class="m3-table-wrap">
        <table class="m3-table">
          <tbody>
            <tr v-for="(h, n) in hits" :key="n" class="hit" @click="open(h)">
              <td>{{ h.program }} · {{ h.name }}</td>
              <td class="num">{{ h.line }}</td>
              <td class="snippet">{{ h.snippet }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-if="viewing" class="viewer">
      <div class="m3-muted">{{ viewing.hit.file }}</div>
      <pre class="code"><span
        v-for="(line, n) in viewing.lines"
        :key="n"
        :ref="(el) => { if (el) lineEls[n] = el as HTMLElement }"
        class="line"
        :class="{ current: n + 1 === viewing.hit.line }"
      ><span class="no">{{ n + 1 }}</span>{{ line || ' ' }}</span></pre>
    </div>
  </div>
</template>

<style scoped>
.title {
  margin: 8px 0 0;
  font-size: 15px;
}

.query {
  flex: 1;
  min-width: 200px;
}

.hit {
  cursor: pointer;
}

.snippet {
  font-family: Consolas, 'Cascadia Mono', monospace;
  font-size: 12px;
}

.viewer {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.code {
  max-height: 360px;
  margin: 0;
  overflow: auto;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: Consolas, 'Cascadia Mono', monospace;
  font-size: 12px;
}

.line {
  display: block;
  padding: 0 8px;
  white-space: pre;
}

.line.current {
  background: var(--active);
  outline: 1px solid var(--accent);
}

.no {
  display: inline-block;
  width: 4ch;
  margin-right: 12px;
  color: var(--text-muted);
  text-align: right;
  user-select: none;
}
</style>
