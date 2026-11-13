<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronRight, FolderPlus, LoaderCircle, Plus, RefreshCw, Settings } from '@lucide/vue'
import { BridgeError, pickFolder, toolCall } from '../../bridge/client'
import { useTool } from '../../bridge/useTool'
import { toastError } from '../../shell/toasts'
import ConfigDialog from './ConfigDialog.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import FolderCard from './FolderCard.vue'
import NewProjectDialog from './NewProjectDialog.vue'
import ProjectCard from './ProjectCard.vue'
import ProjectPanel from './ProjectPanel.vue'
import { breadcrumb, byName, findFolder, findProject, needsTemplateConfirm, searchProjects } from './logic'
import type { Config, EditorView, ProjectEntry, State } from './types'

const PREFIX = 'tools.projects.'
const POLL_MS = 1000

const { t } = useI18n()
const tool = useTool('projects')

const config = ref<Config | null>(null)
const state = ref<State | null>(null)
const editors = ref<EditorView[]>([])
const relPath = ref('')
const query = ref('')
const selected = ref<string | null>(null)
// A selected project that vanished after a rescan stays selected, shown as missing.
const selectedProject = computed<{ project: ProjectEntry; missing: boolean } | null>(() => {
  if (selected.value === null || !tree.value) return null
  const found = findProject(tree.value, selected.value)
  if (found) return { project: found, missing: false }
  const name = selected.value.split('\\').pop() ?? selected.value
  return { project: { name, path: selected.value, rel_path: '', techs: [], is_template: false }, missing: true }
})
const configuring = ref(false)
const newProject = ref(false)
const creating = ref(false)
const pendingOpen = ref<{ path: string; editorId: string } | null>(null)
let pollFailed = false
let pollTimer: ReturnType<typeof setTimeout> | null = null
let unmounted = false

const tree = computed(() => state.value?.tree ?? null)
// A folder that vanished after a rescan falls back to the root.
const current = computed(() => (tree.value ? (findFolder(tree.value, relPath.value) ?? tree.value) : null))
const searching = computed(() => query.value.trim() !== '')
const crumbs = computed(() => (tree.value ? breadcrumb(tree.value, current.value?.rel_path ?? '') : []))
const folders = computed(() => (searching.value ? [] : byName(current.value?.folders ?? [])))
const projects = computed(() => {
  if (!tree.value) return []
  return searching.value ? searchProjects(tree.value, query.value) : byName(current.value?.projects ?? [])
})
const isEmpty = computed(() => folders.value.length === 0 && projects.value.length === 0)
const busy = computed(
  () =>
    !!state.value &&
    (state.value.scanning ||
      state.value.creation?.running === true ||
      Object.values(state.value.git).some((g) => g.running !== null)),
)

// get_state is polled every second while something runs, and not at all otherwise.
// The poll bypasses useTool so that a failing get_state shows one toast per failure streak.
function schedulePoll(): void {
  if (pollTimer !== null || unmounted || !busy.value) return
  pollTimer = setTimeout(async () => {
    pollTimer = null
    try {
      state.value = await toolCall<State>('projects', 'get_state')
      pollFailed = false
    } catch (err) {
      if (!pollFailed) toastError(err, 'projects')
      pollFailed = true
    }
    schedulePoll()
  }, POLL_MS)
}

async function act(action: string, payload: object = {}): Promise<void> {
  try {
    state.value = await tool.call<State>(action, payload)
  } catch {
    // useTool has already shown the error toast.
  }
  schedulePoll()
}

// The git state of the displayed projects is read on demand, after each change of the grid
// (and once a scan has ended: it clears the git cache).
const loadKey = computed(() =>
  state.value?.scanning ? '' : projects.value.map((p) => p.path).join('\n'),
)
watch(loadKey, (key) => {
  if (key) void act('load_status', { paths: projects.value.map((p) => p.path) })
})

async function saveConfig(root: string | null, templatesDir: string | null, maxDepth: number): Promise<void> {
  try {
    config.value = await tool.call<Config>('set_config', {
      root,
      templates_dir: templatesDir,
      max_depth: maxDepth,
    })
  } catch {
    return
  }
  configuring.value = false
  relPath.value = ''
  await act('get_state')
}

async function createProject(template: string, name: string, remoteUrl: string | null): Promise<void> {
  creating.value = true
  try {
    state.value = await tool.call<State>('create_project', {
      template,
      name,
      parent_rel: current.value?.rel_path ?? '',
      remote_url: remoteUrl,
    })
  } catch {
    // useTool has already shown the error toast (invalid name, existing target…).
    creating.value = false
    return
  }
  schedulePoll()
}

// The background creation ended: close the dialog and show the new project, or keep the
// dialog open with the error.
watch(
  () => state.value?.creation,
  async (creation) => {
    if (!creating.value || !creation || creation.running) return
    creating.value = false
    if (creation.error) toastError(new BridgeError(creation.error.code, creation.error.message), 'projects')
    if (creation.created) {
      newProject.value = false
      const project = tree.value ? findProject(tree.value, creation.created) : null
      // The dialog is modal: the folder it was opened from is still the one displayed.
      if (project) {
        query.value = ''
        selected.value = project.path
      }
    }
    await act('clear_creation')
  },
)

async function chooseRoot(): Promise<void> {
  let folder: string | null
  try {
    folder = await pickFolder()
  } catch (err) {
    toastError(err)
    return
  }
  if (folder !== null && config.value) {
    await saveConfig(folder, config.value.templates_dir, config.value.max_depth)
  }
}

function requestOpen(p: ProjectEntry, editorId: string): void {
  if (needsTemplateConfirm(p)) pendingOpen.value = { path: p.path, editorId }
  else void openIn(p.path, editorId)
}

async function confirmOpen(): Promise<void> {
  const pending = pendingOpen.value
  pendingOpen.value = null
  if (pending) await openIn(pending.path, pending.editorId)
}

async function openIn(path: string, editorId: string): Promise<void> {
  try {
    await tool.call('open_in', { path, editor_id: editorId })
  } catch {
    // useTool has already shown the error toast.
  }
}

function enter(path: string): void {
  relPath.value = path
  query.value = ''
}

onMounted(async () => {
  try {
    config.value = await tool.call<Config>('get_config')
    editors.value = await tool.call<EditorView[]>('get_editors')
  } catch {
    // useTool has already shown the error toast.
  }
  if (config.value) await act('get_state')
})
onUnmounted(() => {
  unmounted = true
  if (pollTimer !== null) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="projects">
    <template v-if="config">
      <div v-if="config.root === null" class="empty">
        <p>{{ t(`${PREFIX}empty.noRoot`) }}</p>
        <button type="button" class="primary" @click="chooseRoot">
          <FolderPlus :size="16" aria-hidden="true" />
          {{ t(`${PREFIX}empty.chooseFolder`) }}
        </button>
      </div>

      <div v-else-if="config.root_missing" class="empty">
        <p>{{ t(`${PREFIX}empty.rootMissing`, { root: config.root }) }}</p>
        <button type="button" @click="configuring = true">{{ t(`${PREFIX}empty.settings`) }}</button>
      </div>

      <template v-else>
        <div class="toolbar">
          <nav class="crumbs" :aria-label="t(`${PREFIX}breadcrumb`)">
            <template v-for="(c, i) in crumbs" :key="c.relPath">
              <ChevronRight v-if="i > 0" :size="14" aria-hidden="true" />
              <button type="button" class="crumb" :disabled="i === crumbs.length - 1" @click="enter(c.relPath)">
                {{ c.name }}
              </button>
            </template>
          </nav>
          <input
            v-model="query"
            type="search"
            class="search"
            :placeholder="t(`${PREFIX}toolbar.search`)"
            :aria-label="t(`${PREFIX}toolbar.search`)"
          />
          <button type="button" class="primary" @click="newProject = true">
            <Plus :size="15" aria-hidden="true" />
            {{ t(`${PREFIX}toolbar.newProject`) }}
          </button>
          <button type="button" @click="act('rescan')">
            <RefreshCw :size="15" aria-hidden="true" />
            {{ t(`${PREFIX}toolbar.refresh`) }}
          </button>
          <button type="button" @click="configuring = true">
            <Settings :size="15" aria-hidden="true" />
            {{ t(`${PREFIX}toolbar.settings`) }}
          </button>
        </div>

        <div class="body">
          <div class="main">
            <p v-if="!state || (state.scanning && !tree)" class="empty loading">
              <LoaderCircle :size="16" class="spin" aria-hidden="true" />
              {{ t(`${PREFIX}empty.scanning`) }}
            </p>
            <p v-else-if="state.scan_error" class="empty">
              {{ t(`${PREFIX}empty.scanFailed`, { message: state.scan_error.message }) }}
            </p>
            <p v-else-if="isEmpty" class="empty">
              {{ t(`${PREFIX}empty.${searching ? 'noMatch' : 'emptyFolder'}`) }}
            </p>
            <div v-else class="grid">
              <FolderCard v-for="f in folders" :key="f.rel_path" :folder="f" @open="enter(f.rel_path)" />
              <ProjectCard
                v-for="p in projects"
                :key="p.path"
                :project="p"
                :git="state?.git[p.path]"
                :editors="editors"
                :selected="selected === p.path"
                :show-path="searching"
                @select="selected = p.path"
                @open="(editorId) => requestOpen(p, editorId)"
              />
            </div>
          </div>
          <ProjectPanel
            v-if="selectedProject"
            :key="selectedProject.project.path"
            data-slot="detail"
            :project="selectedProject.project"
            :git="selectedProject.missing ? undefined : state?.git[selectedProject.project.path]"
            :editors="editors"
            :missing="selectedProject.missing"
            @close="selected = null"
            @act="act"
          />
        </div>
      </template>
    </template>

    <ConfirmDialog
      v-if="pendingOpen"
      :message="t(`${PREFIX}confirm.template`)"
      @confirm="confirmOpen"
      @cancel="pendingOpen = null"
    />
    <NewProjectDialog
      v-if="newProject"
      :destination="crumbs.map((c) => c.name).join(' › ')"
      :busy="creating"
      :git-available="state?.git_available ?? true"
      @submit="createProject"
      @cancel="newProject = false"
    />
    <ConfigDialog v-if="configuring && config" :config="config" @save="saveConfig" @cancel="configuring = false" />
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
.crumbs {
  display: flex;
  align-items: center;
  flex: 1;
  gap: 2px;
  color: var(--text-muted);
}
.crumb {
  padding: 3px 6px;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.crumb:hover:not(:disabled) {
  background: var(--hover);
}
.crumb:disabled {
  font-weight: 600;
  cursor: default;
}
.search {
  width: 240px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
}
button:not(.crumb) {
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
button:not(.crumb):hover {
  background: var(--hover);
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
.body {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.main {
  flex: 1;
  min-width: 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.empty {
  color: var(--text-muted);
}
.loading {
  display: flex;
  align-items: center;
  gap: 8px;
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
