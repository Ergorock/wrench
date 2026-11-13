<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, CircleAlert, CircleHelp, Hand, LoaderCircle, TriangleAlert, X } from '@lucide/vue'
import type { RepoView } from '../git_repos/types'
import CommitDialog from '../git_repos/CommitDialog.vue'
import { toolCall } from '../../bridge/client'
import { useTool } from '../../bridge/useTool'
import { toastError } from '../../shell/toasts'
import ConfirmDialog from './ConfirmDialog.vue'
import RemoteDialog from './RemoteDialog.vue'
import { buildDraftChanged, gitBadges, needsTemplateConfirm, requirementIcon, requirementLabelKey } from './logic'
import type { BuildInfo, EditorView, GitView, ProjectEntry, RequirementsView } from './types'

const PREFIX = 'tools.projects.'
const POLL_MS = 1000
const ICONS = { check: Check, alert: TriangleAlert, x: CircleAlert, help: CircleHelp, hand: Hand } as const

const props = defineProps<{
  project: ProjectEntry
  git: GitView | undefined
  editors: EditorView[]
  /** The project vanished from the disk after a rescan: only the error line is shown. */
  missing: boolean
}>()
// `act` carries the actions that answer with the whole state; ProjectsTool applies it.
const emit = defineEmits<{ close: []; act: [action: string, payload: object] }>()

const { t, te } = useI18n()
const tool = useTool('projects')

const pending = ref<(() => Promise<void>) | null>(null)
const committing = ref(false)
const linking = ref(false)
const build = ref<BuildInfo>({ command: null, suggested: null })
const draft = ref('')
const requirements = ref<RequirementsView | null>(null)
let reqTimer: ReturnType<typeof setTimeout> | null = null
let reqFailed = false
// Bumped when the poll must be forgotten (project changed, panel closed): a late answer is ignored.
let reqEpoch = 0

const requirementsError = computed(() => {
  const code = requirements.value?.error?.code
  if (!code) return ''
  return te(`${PREFIX}errors.${code}`) ? t(`${PREFIX}errors.${code}`) : t('errors.generic')
})
const errorText = computed(() => {
  const code = props.git?.error?.code
  if (!code) return ''
  return te(`${PREFIX}errors.${code}`) ? t(`${PREFIX}errors.${code}`) : t('errors.generic')
})
const badges = computed(() => gitBadges(props.git))
const editorTitle = (e: EditorView): string => t(`${PREFIX}editor.${e.available ? 'open' : 'missing'}`, { name: e.name })

async function call(action: string, payload: object = {}): Promise<void> {
  try {
    await tool.call(action, { path: props.project.path, ...payload })
  } catch {
    // useTool has already shown the error toast.
  }
}

function stopRequirements(): void {
  reqEpoch++
  if (reqTimer !== null) clearTimeout(reqTimer)
  reqTimer = null
  reqFailed = false
}

// get_requirements is polled every second while the check runs, and not at all otherwise.
// The poll bypasses useTool so that a failing read shows one toast per failure streak.
function scheduleRequirements(): void {
  if (reqTimer !== null || !requirements.value?.running) return
  const epoch = reqEpoch
  reqTimer = setTimeout(async () => {
    reqTimer = null
    try {
      const view = await toolCall<RequirementsView>('projects', 'get_requirements', { path: props.project.path })
      if (epoch !== reqEpoch) return
      requirements.value = view
      reqFailed = false
    } catch (err) {
      if (epoch !== reqEpoch) return
      if (!reqFailed) toastError(err, 'projects')
      reqFailed = true
    }
    scheduleRequirements()
  }, POLL_MS)
}

async function readRequirements(action: 'check_requirements' | 'get_requirements'): Promise<void> {
  const epoch = reqEpoch
  try {
    const view = await tool.call<RequirementsView>(action, { path: props.project.path })
    if (epoch !== reqEpoch) return
    requirements.value = view
    scheduleRequirements()
  } catch {
    // useTool has already shown the error toast.
  }
}

// A project change forgets the previous project's check; a check already running is picked up again.
function loadRequirements(): void {
  stopRequirements()
  requirements.value = null
  if (!props.missing) void readRequirements('get_requirements')
}

// Everything that opens something goes through the template confirmation.
function guarded(run: () => Promise<void>): void {
  if (needsTemplateConfirm(props.project)) pending.value = run
  else void run()
}
async function confirm(): Promise<void> {
  const run = pending.value
  pending.value = null
  if (run) await run()
}

async function loadBuild(): Promise<void> {
  try {
    build.value = await tool.call<BuildInfo>('get_build', { path: props.project.path })
    draft.value = build.value.command ?? ''
  } catch {
    // useTool has already shown the error toast.
  }
}

// The save in flight: "Lancer" waits for it so that run_build never reads the old command.
let pendingSave: Promise<void> = Promise.resolve()
let queued: string | null = null

function saveBuild(): void {
  const command = draft.value
  if (!buildDraftChanged(build.value, command) || command.trim() === queued) return
  queued = command.trim()
  pendingSave = pendingSave.then(async () => {
    try {
      build.value = await tool.call<BuildInfo>('set_build', { path: props.project.path, command })
      draft.value = build.value.command ?? ''
    } catch {
      // useTool has already shown the error toast.
      queued = null
    }
  })
}

async function runBuild(): Promise<void> {
  saveBuild()
  await pendingSave
  // A failed save leaves the draft unsaved: do not run the old command.
  if (buildDraftChanged(build.value, draft.value)) return
  await call('run_build')
}

function commit(message: string, push: boolean): void {
  committing.value = false
  emit('act', 'commit', { path: props.project.path, message, push })
}
function link(url: string): void {
  linking.value = false
  emit('act', 'set_remote', { path: props.project.path, url })
}

// Escape closes the panel, except when a dialog is open: it closes first.
function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && !document.querySelector('[role="dialog"]')) emit('close')
}
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  if (!props.missing) void loadBuild()
  loadRequirements()
})
watch(() => props.project.path, loadRequirements)
onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  stopRequirements()
})
</script>

<template>
  <aside class="panel">
    <header>
      <div class="title">
        <h2>{{ project.name }}</h2>
        <div class="path">{{ project.path }}</div>
      </div>
      <button type="button" class="icon" :aria-label="t(`${PREFIX}panel.close`)" @click="emit('close')">
        <X :size="16" aria-hidden="true" />
      </button>
    </header>

    <p v-if="missing" class="error">{{ t(`${PREFIX}panel.gone`) }}</p>
    <template v-else>
      <section>
        <h3>{{ t(`${PREFIX}panel.open`) }}</h3>
        <div class="row">
          <button
            v-for="e in editors"
            :key="e.id"
            type="button"
            :title="editorTitle(e)"
            :disabled="!e.available"
            @click="guarded(() => call('open_in', { editor_id: e.id }))"
          >{{ e.name }}</button>
          <button type="button" @click="guarded(() => call('open_explorer'))">{{ t(`${PREFIX}panel.explorer`) }}</button>
          <button type="button" @click="guarded(() => call('open_terminal'))">{{ t(`${PREFIX}panel.terminal`) }}</button>
        </div>
      </section>

      <section>
        <h3>{{ t(`${PREFIX}panel.git`) }}</h3>
        <p v-if="!git" class="muted">{{ t(`${PREFIX}panel.noRepo`) }}</p>
        <template v-else>
          <p class="muted">
            {{ git.branch ?? t(`${PREFIX}panel.detached`) }}
            <span v-for="b in badges" :key="b.kind" class="badge" :class="b.kind">{{ t(`${PREFIX}badges.${b.kind}`, { n: b.n }) }}</span>
          </p>
          <p v-if="git.error" class="error">
            <span :title="git.error.message">{{ errorText }}</span>
            <button type="button" class="link" @click="emit('act', 'clear_error', { path: project.path })">
              {{ t(`${PREFIX}panel.dismissError`) }}
            </button>
          </p>
          <div class="row">
            <button type="button" :disabled="git.running !== null" @click="committing = true">{{ t(`${PREFIX}panel.commit`) }}</button>
            <button
              type="button"
              :disabled="git.running !== null || git.remote_url === null"
              @click="emit('act', 'push', { path: project.path })"
            >{{ t(`${PREFIX}panel.push`) }}</button>
            <button v-if="git.remote_url !== null" type="button" @click="call('open_repo_page')">
              {{ t(`${PREFIX}panel.openRepo`) }}
            </button>
            <button v-else type="button" @click="linking = true">{{ t(`${PREFIX}panel.linkRepo`) }}</button>
          </div>
        </template>
      </section>

      <section>
        <h3>{{ t(`${PREFIX}panel.build`) }}</h3>
        <div class="row">
          <input
            v-model="draft"
            class="build"
            type="text"
            :placeholder="build.suggested ?? ''"
            :aria-label="t(`${PREFIX}panel.buildLabel`)"
            @blur="saveBuild"
            @keydown.enter="saveBuild"
          />
          <button type="button" @click="guarded(runBuild)">{{ t(`${PREFIX}panel.run`) }}</button>
        </div>
      </section>

      <section>
        <h3>{{ t(`${PREFIX}requirements.title`) }}</h3>
        <div class="row">
          <button type="button" :disabled="requirements?.running" @click="readRequirements('check_requirements')">
            {{ t(`${PREFIX}requirements.check`) }}
          </button>
          <span v-if="requirements?.running" class="muted spin">
            <LoaderCircle :size="14" aria-hidden="true" /> {{ t(`${PREFIX}requirements.checking`) }}
          </span>
        </div>
        <p v-if="requirements?.error" class="error">
          <span :title="requirements.error.message">{{ requirementsError }}</span>
        </p>
        <ul v-if="requirements?.items?.length" class="reqs">
          <li v-for="r in requirements.items" :key="r.tool" data-requirement :title="r.source" :class="r.status">
            <component
              :is="ICONS[requirementIcon(r.status) as keyof typeof ICONS]"
              :size="14"
              role="img"
              :aria-label="t(requirementLabelKey(r.status))"
            />
            <span class="tool">{{ r.tool }}</span>
            <span class="muted">{{ t(requirementLabelKey(r.status)) }}</span>
            <span v-if="r.required" class="muted">{{ t(`${PREFIX}requirements.required`, { v: r.required }) }}</span>
            <span v-if="r.installed" class="muted">{{ t(`${PREFIX}requirements.installed`, { v: r.installed }) }}</span>
          </li>
        </ul>
        <p v-else-if="requirements?.items && !requirements.running" class="muted">{{ t(`${PREFIX}requirements.none`) }}</p>
      </section>
    </template>

    <ConfirmDialog v-if="pending" :message="t(`${PREFIX}confirm.template`)" @confirm="confirm" @cancel="pending = null" />
    <CommitDialog
      v-if="committing && git"
      :repo="{ ...git, running: null } as RepoView"
      :can-push="git.remote_url !== null"
      @close="committing = false"
      @submit="commit"
    />
    <RemoteDialog v-if="linking" @submit="link" @cancel="linking = false" />
  </aside>
</template>

<style scoped>
.panel {
  flex: 0 0 320px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
h2 {
  margin: 0;
  font-size: 16px;
  overflow-wrap: anywhere;
}
h3 {
  margin: 0 0 6px;
  font-size: 12px;
  text-transform: uppercase;
  color: var(--text-muted);
}
section {
  margin-top: 14px;
}
.path,
.muted {
  color: var(--text-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
p {
  margin: 0 0 6px;
}
.error {
  color: var(--danger);
}
.badge {
  margin-left: 6px;
}
.badge.conflict,
.badge.error {
  color: var(--danger);
}
.badge.ahead,
.badge.changes {
  color: var(--accent);
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
button {
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: var(--hover);
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
button.icon {
  align-self: flex-start;
  display: inline-flex;
  padding: 4px;
}
button.link {
  padding: 0;
  border: none;
  background: none;
  color: var(--accent);
  text-decoration: underline;
}
.spin {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.spin svg {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.reqs {
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}
.reqs li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}
.reqs .tool {
  font-weight: 600;
}
.reqs .ok svg {
  color: var(--accent);
}
.reqs .missing svg,
.reqs .too_old svg {
  color: var(--danger);
}
.build {
  flex: 1;
  min-width: 0;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
</style>
