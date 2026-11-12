<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Star } from '@lucide/vue'
import { useTool } from '../../bridge/useTool'
import KeyCap from './KeyCap.vue'
import { matches, type SearchEntry } from './search'
import type { Catalog } from './types'

const PREFIX = 'tools.windows_shortcuts.'

const { t, te, locale } = useI18n()
const tool = useTool('windows_shortcuts')

const catalog = ref<Catalog | null>(null)
const favorites = ref<string[]>([])
const query = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

interface Row {
  entry: SearchEntry
  keys: { id: string; label: string }[]
}
interface Section {
  key: string
  label: string
  isFavorites: boolean
  rows: Row[]
}

function keyLabel(id: string): string {
  const key = `${PREFIX}keys.${id}`
  return te(key) ? t(key) : id
}

// Rebuilt when the catalog or the language changes (`locale` is read on purpose).
const rows = computed<Map<string, Row>>(() => {
  void locale.value
  const map = new Map<string, Row>()
  for (const group of catalog.value?.groups ?? []) {
    for (const s of group.shortcuts) {
      const keys = s.keys.map((id) => ({ id, label: keyLabel(id) }))
      map.set(s.id, {
        entry: {
          id: s.id,
          description: t(`${PREFIX}shortcuts.${s.id}`),
          keyLabels: keys.map((k) => k.label),
          keyIds: s.keys,
        },
        keys,
      })
    }
  }
  return map
})

const sections = computed<Section[]>(() => {
  const result: Section[] = []
  const visible = (ids: string[]): Row[] =>
    ids
      .map((id) => rows.value.get(id))
      .filter((r): r is Row => r !== undefined && matches(r.entry, query.value))

  const favRows = visible(favorites.value)
  if (favRows.length > 0) {
    result.push({ key: 'favorites', label: t(`${PREFIX}favorites`), isFavorites: true, rows: favRows })
  }
  for (const group of catalog.value?.groups ?? []) {
    const groupRows = visible(group.shortcuts.map((s) => s.id))
    if (groupRows.length > 0) {
      result.push({
        key: group.id,
        label: t(`${PREFIX}groups.${group.id}`),
        isFavorites: false,
        rows: groupRows,
      })
    }
  }
  return result
})

async function load(): Promise<void> {
  try {
    const data = await tool.call<Catalog>('get_catalog')
    catalog.value = data
    favorites.value = data.favorites
  } catch {
    // useTool has already shown the error toast.
  }
}

async function toggleFavorite(id: string): Promise<void> {
  const previous = favorites.value
  const wanted = !previous.includes(id)
  favorites.value = wanted ? [...previous, id] : previous.filter((f) => f !== id)
  try {
    favorites.value = await tool.call<string[]>('set_favorite', { shortcut_id: id, favorite: wanted })
  } catch {
    // Roll back. useTool has already shown the error toast: no second one here.
    favorites.value = previous
  }
}

function focusSearch(): void {
  searchInput.value?.focus()
  searchInput.value?.select()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.ctrlKey && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'f') {
    event.preventDefault()
    focusSearch()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  searchInput.value?.focus()
  void load()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="shortcuts">
    <input
      ref="searchInput"
      v-model="query"
      type="search"
      class="search"
      :placeholder="t(`${PREFIX}searchPlaceholder`)"
      :aria-label="t(`${PREFIX}searchPlaceholder`)"
    />

    <p v-if="catalog && sections.length === 0" class="empty">{{ t(`${PREFIX}noResults`) }}</p>

    <section v-for="section in sections" :key="section.key" class="group">
      <h2>
        <Star v-if="section.isFavorites" :size="16" class="fav-icon" aria-hidden="true" />
        {{ section.label }}
      </h2>
      <ul>
        <li
          v-for="row in section.rows"
          :key="`${section.key}:${row.entry.id}`"
          :data-shortcut="row.entry.id"
          class="row"
        >
          <span class="description">{{ row.entry.description }}</span>
          <span class="keys">
            <template v-for="(key, index) in row.keys" :key="index">
              <span v-if="index > 0" class="plus" aria-hidden="true">+</span>
              <KeyCap :label="key.label" />
            </template>
          </span>
          <button
            type="button"
            class="star"
            :class="{ on: favorites.includes(row.entry.id) }"
            :aria-pressed="favorites.includes(row.entry.id)"
            :aria-label="t(`${PREFIX}${favorites.includes(row.entry.id) ? 'unpin' : 'pin'}`)"
            :title="t(`${PREFIX}${favorites.includes(row.entry.id) ? 'unpin' : 'pin'}`)"
            @click="toggleFavorite(row.entry.id)"
          >
            <Star :size="16" :fill="favorites.includes(row.entry.id) ? 'currentColor' : 'none'" />
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.shortcuts {
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
.group {
  margin-bottom: 24px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.fav-icon {
  color: var(--accent);
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
.keys {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.plus {
  color: var(--text-muted);
}
.star {
  display: inline-flex;
  padding: 6px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}
.star:hover {
  background: var(--active);
}
.star:focus-visible {
  outline: 2px solid var(--accent);
}
.star.on {
  color: var(--accent);
}
</style>
