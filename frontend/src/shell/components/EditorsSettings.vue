<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { pickExe } from '../../bridge/client'
import type { Editor } from '../../bridge/types'
import { appIcon } from '../appIcons'
import { useShell } from '../state'
import { toastError } from '../toasts'

const { t } = useI18n()
const { settings, update } = useShell()

// `null` while the form is closed, '' while adding a new editor, the editor id while editing.
const editing = ref<string | null>(null)
const name = ref('')
const exe = ref('')
const args = ref('')

function slug(text: string): string {
  const base = text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return base || 'editor'
}

function uniqueId(text: string, taken: string[]): string {
  const base = slug(text)
  let id = base
  for (let n = 2; taken.includes(id); n++) id = `${base}-${n}`
  return id
}

function openForm(editor?: Editor): void {
  editing.value = editor?.id ?? ''
  name.value = editor?.name ?? ''
  exe.value = editor?.exe ?? ''
  args.value = editor ? editor.args.join(' ') : '{path}'
}

function closeForm(): void {
  editing.value = null
}

async function browse(): Promise<void> {
  try {
    const picked = await pickExe(exe.value || undefined)
    if (picked) exe.value = picked
  } catch (err) {
    toastError(err)
  }
}

function save(): void {
  const id = editing.value
  const next = { name: name.value.trim(), exe: exe.value.trim(), args: args.value.split(/\s+/).filter(Boolean) }
  if (id === null || !next.name || !next.exe) return
  void update((s) => {
    const existing = s.editors.find((e) => e.id === id)
    if (existing) Object.assign(existing, next)
    else s.editors.push({ id: uniqueId(next.name, s.editors.map((e) => e.id)), ...next })
  })
  closeForm()
}

function remove(id: string): void {
  void update((s) => {
    s.editors = s.editors.filter((e) => e.id !== id)
  })
  if (editing.value === id) closeForm()
}

function move(id: string, delta: number): void {
  void update((s) => {
    const from = s.editors.findIndex((e) => e.id === id)
    const to = from + delta
    if (from < 0 || to < 0 || to >= s.editors.length) return
    const [item] = s.editors.splice(from, 1)
    s.editors.splice(to, 0, item)
  })
}

const valueOf = (e: Event) => (e.target as HTMLInputElement).value
</script>

<template>
  <div class="card">
    <span class="card-title">{{ t('settings.editors.title') }}</span>
    <span class="hint">{{ t('settings.editors.description') }}</span>
    <p v-if="settings.editors.length === 0" class="hint">{{ t('settings.editors.empty') }}</p>
    <div v-for="(editor, i) in settings.editors" :key="editor.id" class="editor" data-testid="editor-row">
      <img v-if="appIcon(editor.exe).value" :src="appIcon(editor.exe).value ?? ''" alt="" class="icon" />
      <span v-else class="icon" aria-hidden="true"></span>
      <div class="text">
        <span class="editor-name">{{ editor.name }}</span>
        <span class="hint path">{{ editor.exe }}</span>
      </div>
      <button
        type="button"
        class="btn"
        :aria-label="t('settings.editors.moveUp')"
        :disabled="i === 0"
        @click="move(editor.id, -1)"
      >
        ↑
      </button>
      <button
        type="button"
        class="btn"
        :aria-label="t('settings.editors.moveDown')"
        :disabled="i === settings.editors.length - 1"
        @click="move(editor.id, 1)"
      >
        ↓
      </button>
      <button type="button" class="btn" @click="openForm(editor)">{{ t('settings.editors.edit') }}</button>
      <button type="button" class="btn" @click="remove(editor.id)">{{ t('settings.editors.remove') }}</button>
    </div>

    <form v-if="editing !== null" class="editor-form" @submit.prevent="save">
      <label class="field">
        <span>{{ t('settings.editors.name') }}</span>
        <input class="input" type="text" :value="name" @input="name = valueOf($event)" />
      </label>
      <label class="field">
        <span>{{ t('settings.editors.exe') }}</span>
        <span class="row">
          <input class="input grow" type="text" :value="exe" @input="exe = valueOf($event)" />
          <button type="button" class="btn" @click="browse">{{ t('settings.editors.browse') }}</button>
        </span>
      </label>
      <label class="field">
        <span>{{ t('settings.editors.args') }}</span>
        <input class="input" type="text" :value="args" @input="args = valueOf($event)" />
        <span class="hint">{{ t('settings.editors.argsHint') }}</span>
      </label>
      <div class="row">
        <button type="submit" class="btn primary" :disabled="!name.trim() || !exe.trim()">
          {{ t('settings.editors.save') }}
        </button>
        <button type="button" class="btn" @click="closeForm">{{ t('settings.editors.cancel') }}</button>
      </div>
    </form>
    <div v-else>
      <button type="button" class="btn" @click="openForm()">{{ t('settings.editors.add') }}</button>
    </div>
  </div>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.card-title,
.editor-name {
  font-weight: 600;
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.4;
}
.editor {
  display: flex;
  align-items: center;
  gap: 8px;
}
.icon {
  flex: none;
  width: 24px;
  height: 24px;
}
.text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.editor-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.grow {
  flex: 1;
}
.input {
  padding: 6px 10px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 2px);
  font: inherit;
}
.btn {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.btn:hover:not(:disabled) {
  background: var(--hover);
}
.btn:disabled {
  color: var(--text-muted);
  cursor: default;
}
.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
</style>
