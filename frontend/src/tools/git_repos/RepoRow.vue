<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { GitBranch, GitFork, History, LoaderCircle, X } from '@lucide/vue'
import { availableActions, branchTitle, changeCount, hostTitle, isUnpublished, needsAttention, relativeTime } from './logic'
import type { RepoView } from './types'

const PREFIX = 'tools.git_repos.'

const props = defineProps<{ repo: RepoView; now: Date }>()
const emit = defineEmits<{
  fetch: []
  pull: []
  push: []
  commit: []
  clearError: []
  branches: []
  history: []
}>()

const { t, te } = useI18n()
const tt = (key: string, params: object = {}): string =>
  t(`${PREFIX}${key}`, params as Record<string, unknown>)

const actions = computed(() => availableActions(props.repo))
const changes = computed(() => changeCount(props.repo))
// GitHub has no Lucide icon (brand icons were removed): GitBranch stands for it.
const hostIcon = computed(() => (props.repo.host === 'github' ? GitBranch : GitFork))
const hostText = computed(() => hostTitle(props.repo, tt))
const fetched = computed(() => tt('badges.fetched', { when: relativeTime(props.repo.last_fetch, props.now, tt) }))
const errorText = computed(() => {
  const code = props.repo.error?.code
  if (!code) return ''
  const key = `${PREFIX}errors.${code}`
  return te(key) ? t(key) : t('errors.generic')
})
</script>

<template>
  <li class="repo" :data-repo="repo.path">
    <div class="identity">
      <div class="title">
        <span v-if="repo.host !== 'none'" class="host" :title="hostText">
          <component :is="hostIcon" :size="15" role="img" :aria-label="hostText" />
        </span>
        <span class="name">{{ repo.name }}</span>
        <span v-if="repo.rel_path !== repo.name" class="rel">{{ repo.rel_path }}</span>
      </div>
      <div class="meta">
        <button type="button" class="branch" :title="branchTitle(repo, tt)" @click="emit('branches')">
          <GitBranch :size="13" aria-hidden="true" />
          {{ repo.detached ? tt('badges.detached') : repo.branch }}
        </button>
        <span v-if="repo.remote_url" class="fetched">{{ fetched }}</span>
      </div>
    </div>

    <div class="badges">
      <button v-if="repo.ahead > 0" type="button" class="badge accent" :title="tt('badges.aheadTitle', { n: repo.ahead })" @click="emit('history')">
        {{ tt('badges.ahead', { n: repo.ahead }) }}
      </button>
      <span v-if="repo.behind > 0" class="badge accent" :title="tt('badges.behindTitle', { n: repo.behind })">
        {{ tt('badges.behind', { n: repo.behind }) }}
      </span>
      <span v-if="changes > 0" class="badge warn" :title="tt('badges.changesTitle', { n: changes })">
        {{ tt('badges.changes', { n: changes }) }}
      </span>
      <span v-if="repo.conflicts > 0" class="badge danger" :title="tt('badges.conflictTitle')">{{ tt('badges.conflict') }}</span>
      <span v-if="repo.operation" class="badge danger" :title="tt('badges.operationTitle', { op: repo.operation })">{{ tt('badges.operation', { op: repo.operation }) }}</span>
      <span v-if="repo.detached" class="badge" :title="tt('badges.detachedTitle')">{{ tt('badges.detached') }}</span>
      <span v-if="!repo.remote_url" class="badge" :title="tt('badges.noRemoteTitle')">{{ tt('badges.noRemote') }}</span>
      <span v-if="isUnpublished(repo)" class="badge accent" :title="tt('badges.unpublishedTitle')">{{ tt('badges.unpublished') }}</span>
      <span v-if="!needsAttention(repo)" class="badge ok" :title="tt('badges.upToDateTitle')">{{ tt('badges.upToDate') }}</span>
      <span v-if="repo.error" class="badge danger error" :title="tt('badges.errorTitle', { message: repo.error.message })">
        {{ errorText }}
        <button type="button" class="clear" :aria-label="tt('badges.clearError')" :title="tt('badges.clearError')" @click="emit('clearError')">
          <X :size="12" />
        </button>
      </span>
    </div>

    <div class="buttons">
      <button type="button" class="history" :title="tt('actions.historyTitle')" @click="emit('history')">
        <History :size="14" aria-hidden="true" />
        {{ tt('actions.history') }}
      </button>
      <span v-if="repo.running" class="running">
        <LoaderCircle :size="15" class="spin" aria-hidden="true" />
        {{ tt(`actions.running.${repo.running}`) }}
      </span>
      <template v-else>
        <button type="button" :disabled="!actions.fetch" @click="emit('fetch')">{{ tt('actions.fetch') }}</button>
        <button type="button" :disabled="!actions.pull" @click="emit('pull')">{{ tt('actions.pull') }}</button>
        <button type="button" :disabled="!actions.push" @click="emit('push')">{{ tt('actions.push') }}</button>
        <button type="button" :disabled="!actions.commit" @click="emit('commit')">{{ tt('actions.commit') }}</button>
      </template>
    </div>
  </li>
</template>

<style scoped>
.repo {
  display: grid;
  grid-template-columns: minmax(180px, 1.2fr) minmax(160px, 1.5fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}
.repo:last-child {
  border-bottom: none;
}
.title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}
.host {
  align-self: center;
  color: var(--text-muted);
  flex-shrink: 0;
}
.name {
  font-weight: 600;
}
.rel,
.meta {
  color: var(--text-muted);
  font-size: 12px;
}
.rel {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  display: flex;
  gap: 12px;
  margin-top: 2px;
}
.branch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.branch:hover {
  color: var(--text);
  text-decoration: underline;
}
.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  color: var(--text-muted);
}
button.badge {
  background: none;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
button.badge:hover {
  background: var(--hover);
}
.badge.accent {
  color: var(--accent);
  border-color: var(--accent);
}
.badge.warn {
  color: var(--text);
  background: var(--warning-bg);
  border-color: var(--warning-border);
}
.badge.danger {
  color: var(--danger);
  border-color: var(--danger);
}
.badge.error {
  max-width: 100%;
  white-space: normal;
}
.clear {
  display: inline-flex;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  cursor: pointer;
}
.buttons {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
.buttons button {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.buttons .history {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.buttons button:hover:not(:disabled) {
  background: var(--hover);
}
.buttons button:disabled {
  opacity: 0.45;
  cursor: default;
}
.running {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 13px;
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
