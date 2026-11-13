<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LoaderCircle, X } from '@lucide/vue'
import { useTool } from '../../bridge/useTool'
import { relativeTime } from './logic'
import type { CommitInfo, RepoView } from './types'

const PREFIX = 'tools.git_repos.'
const PAGE = 50 // page size of get_commits

/** `gitRef`: a branch name, or null for the current branch. */
const props = defineProps<{ repo: RepoView; gitRef: string | null; now: Date }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const tt = (key: string, params: object = {}): string => t(`${PREFIX}${key}`, params as Record<string, unknown>)
const tool = useTool('git_repos')

const commits = ref<CommitInfo[]>([])
const loading = ref(false)
const hasMore = ref(false)
const closeButton = ref<HTMLButtonElement | null>(null)
const previousFocus = document.activeElement as HTMLElement | null

const subtitle = computed(() => {
  if (props.gitRef !== null) return props.gitRef
  if (props.repo.detached || props.repo.branch === null) return tt('history.detached')
  return `${props.repo.branch} (${tt('history.current')})`
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const page = await tool.call<CommitInfo[]>('get_commits', {
      path: props.repo.path,
      ref: props.gitRef,
      skip: commits.value.length,
    })
    commits.value = [...commits.value, ...page]
    hasMore.value = page.length === PAGE
  } catch {
    // useTool has already shown the error toast.
    if (commits.value.length === 0) emit('close')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  closeButton.value?.focus()
  void load()
})
onUnmounted(() => previousFocus?.focus())
</script>

<template>
  <div class="overlay" @click.self="emit('close')" @keydown.esc.stop="emit('close')">
    <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="git-repos-history-title">
      <header>
        <div>
          <h2 id="git-repos-history-title">{{ tt('history.title', { name: repo.name }) }}</h2>
          <p class="muted ref">{{ subtitle }}</p>
        </div>
        <button ref="closeButton" type="button" class="close" :aria-label="tt('dialog.close')" :title="tt('dialog.close')" @click="emit('close')">
          <X :size="16" />
        </button>
      </header>

      <p v-if="!loading && commits.length === 0" class="muted">{{ tt('history.empty') }}</p>
      <ol class="list">
        <li v-for="c in commits" :key="c.hash" class="commit" :title="c.message">
          <span class="mark" :title="c.unpushed ? tt('history.unpushedTitle') : undefined">
            <template v-if="c.unpushed">↑<span class="sr-only">{{ tt('history.unpushedTitle') }}</span></template>
          </span>
          <code class="hash">{{ c.short_hash }}</code>
          <span class="subject">{{ c.subject }}</span>
          <span class="author">{{ c.author }}</span>
          <span class="date">{{ relativeTime(c.date, now, tt) }}</span>
        </li>
      </ol>

      <p v-if="loading" class="muted loading">
        <LoaderCircle :size="15" class="spin" aria-hidden="true" />
        {{ tt('dialog.loading') }}
      </p>
      <button v-else-if="hasMore" type="button" class="more" @click="load">{{ tt('history.more') }}</button>
    </section>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--active);
  z-index: 60;
}
.dialog {
  display: flex;
  flex-direction: column;
  width: min(820px, calc(100vw - 48px));
  max-height: calc(100vh - 64px);
  overflow: auto;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  box-shadow: var(--shadow);
}
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.close {
  display: inline-flex;
  padding: 4px;
  border: none;
  border-radius: var(--radius);
  background: none;
  color: var(--text-muted);
  cursor: pointer;
}
.close:hover {
  background: var(--hover);
}
.muted {
  margin: 8px 0 0;
  color: var(--text-muted);
}
.ref {
  margin-top: 2px;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.loading {
  display: flex;
  align-items: center;
  gap: 8px;
}
.list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}
.commit {
  display: grid;
  grid-template-columns: 14px auto minmax(0, 1fr) auto auto;
  align-items: baseline;
  gap: 10px;
  padding: 5px 4px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.commit:last-child {
  border-bottom: none;
}
.mark {
  color: var(--accent);
  font-weight: 600;
}
.hash {
  color: var(--text-muted);
  font-family: Consolas, monospace;
  font-size: 12px;
}
.subject {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.author,
.date {
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
}
.more {
  align-self: center;
  margin-top: 12px;
  padding: 5px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.more:hover {
  background: var(--hover);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
