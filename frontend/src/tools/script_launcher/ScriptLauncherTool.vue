<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import { pickExe, pickFolder } from '../../bridge/client'
import type { Command, Commands, RunResult } from './types'

const PREFIX = 'tools.script_launcher.'

const { t } = useI18n()
const tool = useTool('script_launcher')

const commands = ref<Command[]>([])
const running = ref<string | null>(null)
const result = ref<{ name: string; run: RunResult } | null>(null)
const confirmDelete = ref<string | null>(null)

// The form is shared by "new" (editing = null) and "edit" (editing = the saved command).
const editing = ref<Command | null>(null)
const formOpen = ref(false)
const form = ref({ name: '', program: '', argsText: '', cwd: '' })

function openNew(): void {
  editing.value = null
  form.value = { name: '', program: '', argsText: '', cwd: '' }
  formOpen.value = true
}

function openEdit(command: Command): void {
  editing.value = command
  form.value = {
    name: command.name,
    program: command.program,
    argsText: command.args.join('\n'),
    cwd: command.cwd,
  }
  formOpen.value = true
}

function closeForm(): void {
  formOpen.value = false
  editing.value = null
}

async function choose(field: 'program' | 'cwd'): Promise<void> {
  const picked = field === 'program' ? await pickExe(form.value.program) : await pickFolder(form.value.cwd)
  if (picked !== null) form.value[field] = picked
}

async function load(): Promise<void> {
  try {
    commands.value = (await tool.call<Commands>('list_commands')).commands
  } catch {
    // useTool has already shown the error toast.
  }
}

async function save(): Promise<void> {
  const args = form.value.argsText
    .split('\n')
    .map((a) => a.trim())
    .filter((a) => a !== '')
  try {
    const data = await tool.call<Commands>('save_command', {
      command: {
        id: editing.value?.id ?? '',
        name: form.value.name,
        program: form.value.program,
        args,
        cwd: form.value.cwd,
      },
    })
    commands.value = data.commands
    closeForm()
  } catch {
    // useTool has already shown the error toast; the form stays open.
  }
}

async function remove(id: string): Promise<void> {
  try {
    commands.value = (await tool.call<Commands>('delete_command', { command_id: id })).commands
  } catch {
    // useTool has already shown the error toast.
  } finally {
    confirmDelete.value = null
  }
}

async function run(command: Command): Promise<void> {
  running.value = command.id
  result.value = null
  try {
    result.value = { name: command.name, run: await tool.call<RunResult>('run_command', { command_id: command.id }) }
  } catch {
    // useTool has already shown the error toast.
  } finally {
    running.value = null
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="launcher">
    <div class="top">
      <p class="hint">{{ t(`${PREFIX}intro`) }}</p>
      <button type="button" class="button primary" :disabled="formOpen" @click="openNew">
        {{ t(`${PREFIX}add`) }}
      </button>
    </div>

    <form v-if="formOpen" class="panel form" @submit.prevent="save">
      <label class="field">
        <span>{{ t(`${PREFIX}nameLabel`) }}</span>
        <input v-model="form.name" maxlength="60" required />
      </label>
      <label class="field">
        <span>{{ t(`${PREFIX}program`) }}</span>
        <div class="row-inline">
          <input v-model="form.program" maxlength="260" required />
          <button type="button" class="button" @click="choose('program')">
            {{ t(`${PREFIX}browse`) }}
          </button>
        </div>
        <small class="hint">{{ t(`${PREFIX}programHint`) }}</small>
      </label>
      <label class="field">
        <span>{{ t(`${PREFIX}args`) }}</span>
        <textarea v-model="form.argsText" rows="3" :placeholder="t(`${PREFIX}argsPlaceholder`)" />
      </label>
      <label class="field">
        <span>{{ t(`${PREFIX}cwd`) }}</span>
        <div class="row-inline">
          <input v-model="form.cwd" />
          <button type="button" class="button" @click="choose('cwd')">
            {{ t(`${PREFIX}browse`) }}
          </button>
        </div>
      </label>
      <div class="row-inline">
        <button type="submit" class="button primary">{{ t(`${PREFIX}save`) }}</button>
        <button type="button" class="button" @click="closeForm">{{ t(`${PREFIX}cancel`) }}</button>
      </div>
    </form>

    <p v-if="commands.length === 0 && !formOpen" class="hint">{{ t(`${PREFIX}empty`) }}</p>

    <ul v-if="commands.length > 0" class="list">
      <li v-for="c in commands" :key="c.id" :data-command="c.name" class="item">
        <div class="info">
          <strong>{{ c.name }}</strong>
          <code class="cmd">{{ c.program }} {{ c.args.join(' ') }}</code>
          <small v-if="c.cwd" class="hint">{{ t(`${PREFIX}inFolder`, { folder: c.cwd }) }}</small>
        </div>
        <div class="actions">
          <button
            type="button"
            class="button primary"
            :disabled="running !== null"
            @click="run(c)"
          >
            {{ running === c.id ? t(`${PREFIX}running`) : t(`${PREFIX}run`) }}
          </button>
          <button type="button" class="button" :disabled="running !== null" @click="openEdit(c)">
            {{ t(`${PREFIX}edit`) }}
          </button>
          <template v-if="confirmDelete === c.id">
            <button type="button" class="button danger" @click="remove(c.id)">
              {{ t(`${PREFIX}confirmDelete`) }}
            </button>
            <button type="button" class="button" @click="confirmDelete = null">
              {{ t(`${PREFIX}cancel`) }}
            </button>
          </template>
          <button v-else type="button" class="button" @click="confirmDelete = c.id">
            {{ t(`${PREFIX}delete`) }}
          </button>
        </div>
      </li>
    </ul>

    <section v-if="result" class="panel output" data-testid="output">
      <h2>{{ result.name }}</h2>
      <p v-if="result.run.timed_out" class="warning">{{ t(`${PREFIX}timedOut`) }}</p>
      <p v-else class="hint">{{ t(`${PREFIX}exitCode`, { code: result.run.exit_code ?? '—' }) }}</p>
      <pre v-if="result.run.stdout">{{ result.run.stdout }}</pre>
      <pre v-if="result.run.stderr" class="stderr">{{ result.run.stderr }}</pre>
    </section>
  </div>
</template>

<style scoped>
.launcher {
  max-width: 820px;
}
.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}
.panel {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--text-muted);
}
.row-inline {
  display: flex;
  gap: 8px;
  align-items: center;
}
.row-inline input {
  flex: 1;
}
input,
textarea {
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
textarea {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  resize: vertical;
}
.button {
  padding: 7px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--active);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.button.primary {
  background: var(--accent);
  color: var(--accent-text);
  border-color: transparent;
}
.button.danger {
  border-color: var(--danger);
  color: var(--danger);
}
.button:disabled {
  opacity: 0.5;
  cursor: default;
}
.button:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.list {
  margin: 0 0 16px;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px;
}
.item + .item {
  border-top: 1px solid var(--border);
}
.info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cmd {
  overflow-wrap: anywhere;
  font-size: 13px;
  color: var(--text-muted);
}
.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.output h2 {
  margin: 0 0 8px;
  font-size: 15px;
}
pre {
  margin: 8px 0 0;
  padding: 10px;
  max-height: 320px;
  overflow: auto;
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.stderr {
  color: var(--danger);
}
.warning {
  margin: 0;
  color: var(--danger);
  font-weight: 600;
}
</style>
