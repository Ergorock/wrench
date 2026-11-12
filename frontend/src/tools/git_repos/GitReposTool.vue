<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, FolderPlus, RefreshCw, Settings } from '@lucide/vue'
import { pickFolder } from '../../bridge/client'
import { useTool } from '../../bridge/useTool'
import { toastError } from '../../shell/toasts'
import CommitDialog from './CommitDialog.vue'
import FoldersView from './FoldersView.vue'
import RepoRow from './RepoRow.vue'
import { filterRepos, sortRepos } from './logic'
import type { RepoConfig, RepoState, RepoView } from './types'

const PREFIX = 'tools.git_repos.'
const POLL_MS = 1000

const { t } = useI18n()
const tool = useTool('git_repos')

const config = ref<RepoConfig | null>(null)
const state = ref<RepoState | null>(null)
const view = ref<'list' | 'folders'>('list')
const query = ref('')
const onlyAttention = ref(false)
const committing = ref<RepoView | null>(null)
const now = ref(new Date())
let pollTimer: ReturnType<typeof setTimeout> | null = null
let unmounted = false

const groups = computed(() => {
  const repos = filterRepos(state.value?.repos ?? [], query.value, onlyAttention.value)
  return (config.value?.roots ?? [])
    .map((root) => ({ root, repos: sortRepos(repos.filter((r) => r.root === root)) }))
    .filter((g) => g.repos.length > 0)
})
const hasRepos = computed(() => (state.value?.repos.length ?? 0) > 0)

// get_state is polled every second while an operation runs, and not at all otherwise.
function schedulePoll(): void {
  if (pollTimer !== null || unmounted || !state.value?.repos.some((r) => r.running)) return
  pollTimer = setTimeout(async () => {
    pollTimer = null
    await run(() => tool.call<RepoState>('get_state'))
  }, POLL_MS)
}

async function run(call: () => Promise<RepoState>): Promise<void> {
  try {
    state.value = await call()
  } catch {
    // useTool has already shown the error toast.
  }
  now.value = new Date()
  schedulePoll()
}

const act = (action: string, payload: object = {}): Promise<void> =>
  run(() => tool.call<RepoState>(action, payload))

async function open(): Promise<void> {
  try {
    config.value = await tool.call<RepoConfig>('get_config')
  } catch {
    return
  }
  await act('rescan')
  if (state.value?.git_available && hasRepos.value) await act('fetch_all')
}

async function saveFolders(roots: string[], maxDepth: number): Promise<void> {
  try {
    config.value = await tool.call<RepoConfig>('set_config', { roots, max_depth: maxDepth })
  } catch {
    return
  }
  view.value = 'list'
  await act('get_state')
}

async function addFirstFolder(): Promise<void> {
  let folder: string | null
  try {
    folder = await pickFolder()
  } catch (err) {
    toastError(err)
    return
  }
  if (folder === null || config.value === null) return
  await saveFolders([folder], config.value.max_depth)
  if (state.value?.git_available && hasRepos.value) await act('fetch_all')
}

async function commit(message: string, push: boolean): Promise<void> {
  const repo = committing.value
  committing.value = null
  if (repo) await act('commit', { path: repo.path, message, push })
}

onMounted(() => void open())
onUnmounted(() => {
  unmounted = true
  if (pollTimer !== null) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="git-repos">
    <FoldersView
      v-if="view === 'folders' && config"
      :config="config"
      @save="saveFolders"
      @cancel="view = 'list'"
    />

    <template v-else-if="config">
      <div v-if="state && !state.git_available" class="notice">
        <p>{{ t(`${PREFIX}empty.noGit`) }}</p>
        <code>winget install Git.Git</code>
      </div>

      <div v-if="config.roots.length === 0" class="empty">
        <p>{{ t(`${PREFIX}empty.noRoots`) }}</p>
        <button type="button" class="primary" @click="addFirstFolder">
          <FolderPlus :size="16" aria-hidden="true" />
          {{ t(`${PREFIX}empty.addFolder`) }}
        </button>
      </div>

      <template v-else>
        <div class="toolbar">
          <input
            v-model="query"
            type="search"
            class="search"
            :placeholder="t(`${PREFIX}toolbar.search`)"
            :aria-label="t(`${PREFIX}toolbar.search`)"
          />
          <div class="segmented" role="group">
            <button type="button" :class="{ on: !onlyAttention }" @click="onlyAttention = false">
              {{ t(`${PREFIX}toolbar.all`) }}
            </button>
            <button type="button" :class="{ on: onlyAttention }" @click="onlyAttention = true">
              {{ t(`${PREFIX}toolbar.attention`) }}
            </button>
          </div>
          <span class="spacer" />
          <button type="button" :disabled="!state?.git_available || !hasRepos" @click="act('fetch_all')">
            <Download :size="15" aria-hidden="true" />
            {{ t(`${PREFIX}toolbar.fetchAll`) }}
          </button>
          <button type="button" @click="act('rescan')">
            <RefreshCw :size="15" aria-hidden="true" />
            {{ t(`${PREFIX}toolbar.refresh`) }}
          </button>
          <button type="button" @click="view = 'folders'">
            <Settings :size="15" aria-hidden="true" />
            {{ t(`${PREFIX}toolbar.folders`) }}
          </button>
        </div>

        <div v-if="state && !hasRepos" class="empty">
          <p>{{ t(`${PREFIX}empty.noRepos`) }}</p>
          <button type="button" @click="view = 'folders'">{{ t(`${PREFIX}empty.openFolders`) }}</button>
        </div>
        <p v-else-if="state && groups.length === 0" class="empty">{{ t(`${PREFIX}empty.noMatch`) }}</p>

        <section v-for="group in groups" :key="group.root" class="group">
          <h2>{{ group.root }}</h2>
          <ul>
            <RepoRow
              v-for="repo in group.repos"
              :key="repo.path"
              :repo="repo"
              :now="now"
              @fetch="act('fetch', { path: repo.path })"
              @pull="act('pull', { path: repo.path })"
              @push="act('push', { path: repo.path })"
              @commit="committing = repo"
              @clear-error="act('clear_error', { path: repo.path })"
            />
          </ul>
        </section>
      </template>
    </template>

    <CommitDialog
      v-if="committing"
      :repo="committing"
      :can-push="committing.remote_url !== null"
      @close="committing = null"
      @submit="commit"
    />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.search {
  width: 260px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
}
.spacer {
  flex: 1;
}
button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: var(--hover);
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
.segmented {
  display: inline-flex;
}
.segmented button {
  border-radius: 0;
}
.segmented button:first-child {
  border-radius: var(--radius) 0 0 var(--radius);
}
.segmented button:last-child {
  border-radius: 0 var(--radius) var(--radius) 0;
  border-left: none;
}
.segmented button.on {
  background: var(--active);
  font-weight: 600;
}
.group {
  margin-bottom: 20px;
}
.group h2 {
  margin: 0 0 6px;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.group ul {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.empty {
  color: var(--text-muted);
}
.notice {
  margin-bottom: 16px;
  padding: 10px 14px;
  border: 1px solid var(--warning-border);
  border-radius: var(--radius);
  background: var(--warning-bg);
}
.notice p {
  margin: 0 0 6px;
}
</style>
