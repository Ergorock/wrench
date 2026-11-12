<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LoaderCircle, X } from '@lucide/vue'
import { useTool } from '../../bridge/useTool'
import { mergeLabel, relativeTime } from './logic'
import type { BranchList, LocalBranch, RepoView } from './types'

const PREFIX = 'tools.git_repos.'

const props = defineProps<{ repo: RepoView; now: Date }>()
const emit = defineEmits<{ close: []; open: [ref: string] }>()

const { t } = useI18n()
const tt = (key: string, params: object = {}, n?: number): string =>
  n === undefined ? t(`${PREFIX}${key}`, params as Record<string, unknown>) : t(`${PREFIX}${key}`, params as Record<string, unknown>, n)
const tool = useTool('git_repos')

const branches = ref<BranchList | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const previousFocus = document.activeElement as HTMLElement | null

const when = (iso: string | null): string => tt('branches.lastCommit', { when: relativeTime(iso, props.now, tt) })

function mergeTitle(b: LocalBranch): string {
  const main = branches.value?.main ?? ''
  if (b.merged) return tt('branches.mergedTitle', { main })
  return tt('branches.notInMainTitle', { n: b.commits_not_in_main, main })
}

onMounted(async () => {
  closeButton.value?.focus()
  try {
    branches.value = await tool.call<BranchList>('get_branches', { path: props.repo.path })
  } catch {
    emit('close') // useTool has already shown the error toast.
  }
})
onUnmounted(() => previousFocus?.focus())
</script>

<template>
  <div class="overlay" @click.self="emit('close')" @keydown.esc.stop="emit('close')">
    <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="git-repos-branches-title">
      <header>
        <h2 id="git-repos-branches-title">{{ tt('branches.title', { name: repo.name }) }}</h2>
        <button ref="closeButton" type="button" class="close" :aria-label="tt('dialog.close')" :title="tt('dialog.close')" @click="emit('close')">
          <X :size="16" />
        </button>
      </header>

      <p v-if="!branches" class="muted loading">
        <LoaderCircle :size="15" class="spin" aria-hidden="true" />
        {{ tt('dialog.loading') }}
      </p>
      <template v-else>
        <p class="muted">{{ branches.main ? tt('branches.main', { main: branches.main }) : tt('branches.noMain') }}</p>

        <h3>{{ tt('branches.local', { n: branches.local.length }) }}</h3>
        <p v-if="branches.local.length === 0" class="muted">{{ tt('branches.empty') }}</p>
        <ul class="list">
          <li v-for="b in branches.local" :key="b.name">
            <button type="button" class="item" :title="tt('branches.open', { name: b.name })" @click="emit('open', b.name)">
              <span class="name" :class="{ current: b.current }">{{ b.name }}</span>
              <span v-if="b.current" class="tag">{{ tt('branches.current') }}</span>
              <span v-if="b.name === branches.main" class="tag">{{ tt('branches.isMain') }}</span>
              <span v-if="b.ahead > 0" class="count accent" :title="tt('branches.aheadTitle', { n: b.ahead, upstream: b.upstream })">
                {{ tt('badges.ahead', { n: b.ahead }) }}
              </span>
              <span v-if="b.behind > 0" class="count accent" :title="tt('branches.behindTitle', { n: b.behind, upstream: b.upstream })">
                {{ tt('badges.behind', { n: b.behind }) }}
              </span>
              <span v-if="mergeLabel(b, tt)" class="count" :class="b.merged ? 'ok' : 'accent'" :title="mergeTitle(b)">
                {{ mergeLabel(b, tt) }}
              </span>
              <span class="date">{{ when(b.last_commit) }}</span>
            </button>
          </li>
        </ul>

        <details v-if="branches.remote.length > 0">
          <summary>{{ tt('branches.remote', { n: branches.remote.length }) }}</summary>
          <ul class="list">
            <li v-for="b in branches.remote" :key="b.name">
              <button type="button" class="item" :title="tt('branches.open', { name: b.name })" @click="emit('open', b.name)">
                <span class="name">{{ b.name }}</span>
                <span class="date">{{ when(b.last_commit) }}</span>
              </button>
            </li>
          </ul>
        </details>
      </template>
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
  z-index: 50;
}
.dialog {
  display: flex;
  flex-direction: column;
  width: min(640px, calc(100vw - 48px));
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
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
h3 {
  margin: 12px 0 4px;
  font-size: 13px;
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
.loading {
  display: flex;
  align-items: center;
  gap: 8px;
}
summary {
  margin-top: 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.list {
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
}
.item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-radius: var(--radius);
  background: none;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.item:hover {
  background: var(--hover);
}
.name {
  overflow-wrap: anywhere;
}
.name.current {
  font-weight: 600;
}
.tag {
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
  font-size: 11px;
}
.count {
  font-size: 12px;
  white-space: nowrap;
}
.count.accent {
  color: var(--accent);
}
.count.ok {
  color: var(--text-muted);
}
.date {
  margin-left: auto;
  color: var(--text-muted);
  font-size: 12px;
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
