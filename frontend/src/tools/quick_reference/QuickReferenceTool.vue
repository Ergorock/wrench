<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import { matches } from './filter'
import type { Reference } from './types'

const PREFIX = 'tools.quick_reference.'

const { t, te } = useI18n()
const tool = useTool('quick_reference')

const reference = ref<Reference | null>(null)
const query = ref('')

function describe(id: string): string {
  return te(`${PREFIX}entries.${id}`) ? t(`${PREFIX}entries.${id}`) : id
}

const sections = computed(() =>
  (reference.value?.sheets ?? [])
    .map((sheet) => ({
      id: sheet.id,
      title: t(`${PREFIX}sheets.${sheet.id}`),
      rows: sheet.entries
        .map((e) => ({ id: e.id, command: e.command, description: describe(e.id) }))
        .filter((r) => matches(r.description, r.command, query.value)),
    }))
    .filter((s) => s.rows.length > 0),
)

async function load(): Promise<void> {
  try {
    reference.value = await tool.call<Reference>('get_sheets')
  } catch {
    // useTool has already shown the error toast.
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="reference">
    <input
      v-model="query"
      type="search"
      class="search"
      :placeholder="t(`${PREFIX}searchPlaceholder`)"
      :aria-label="t(`${PREFIX}searchPlaceholder`)"
    />

    <p v-if="reference && sections.length === 0" class="empty">{{ t(`${PREFIX}noResults`) }}</p>

    <section v-for="section in sections" :key="section.id" class="sheet">
      <h2>{{ section.title }}</h2>
      <ul>
        <li v-for="row in section.rows" :key="row.id" :data-entry="row.id" class="row">
          <span class="description">{{ row.description }}</span>
          <code class="command">{{ row.command }}</code>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.reference {
  max-width: 880px;
}
.search {
  box-sizing: border-box;
  width: 100%;
  margin-bottom: 20px;
  padding: 9px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
}
.search:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.empty {
  color: var(--text-muted);
}
.sheet {
  margin-bottom: 24px;
}
h2 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 12px;
}
.row + .row {
  border-top: 1px solid var(--border);
}
.row:hover {
  background: var(--hover);
}
.description {
  flex: 1;
  min-width: 0;
}
.command {
  flex-shrink: 0;
  max-width: 55%;
  overflow-wrap: anywhere;
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  color: var(--text);
}
</style>
