<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { pickFolder } from '../../bridge/client'
import { toastError } from '../../shell/toasts'
import type { Config } from './types'

const PREFIX = 'tools.projects.'
const DEPTHS = [1, 2, 3, 4, 5, 6]

const props = defineProps<{ config: Config }>()
const emit = defineEmits<{
  save: [root: string | null, templatesDir: string | null, maxDepth: number]
  cancel: []
}>()

const { t } = useI18n()
const root = ref(props.config.root ?? '')
const templates = ref(props.config.templates_dir ?? '')
const depth = ref(props.config.max_depth)

const fields = { root, templates }

async function browse(field: keyof typeof fields): Promise<void> {
  try {
    const folder = await pickFolder(fields[field].value || undefined)
    if (folder !== null) fields[field].value = folder
  } catch (err) {
    // pickFolder is a shell call, not a tool action: nothing has shown this error yet.
    toastError(err)
  }
}

const orNull = (s: string): string | null => s.trim() || null
</script>

<template>
  <div class="overlay" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
    <form
      class="dialog"
      role="dialog"
      aria-modal="true"
      @submit.prevent="emit('save', orNull(root), orNull(templates), depth)"
    >
      <h2>{{ t(`${PREFIX}config.title`) }}</h2>
      <label>
        {{ t(`${PREFIX}config.root`) }}
        <span class="row">
          <input v-model="root" type="text" />
          <button type="button" @click="browse('root')">{{ t(`${PREFIX}config.browse`) }}</button>
        </span>
      </label>
      <label>
        {{ t(`${PREFIX}config.templates`) }}
        <span class="row">
          <input v-model="templates" type="text" />
          <button type="button" @click="browse('templates')">{{ t(`${PREFIX}config.browse`) }}</button>
        </span>
        <span class="hint">{{ t(`${PREFIX}config.templatesHint`) }}</span>
      </label>
      <label>
        {{ t(`${PREFIX}config.depth`) }}
        <select v-model.number="depth">
          <option v-for="d in DEPTHS" :key="d" :value="d">{{ d }}</option>
        </select>
      </label>
      <div class="buttons">
        <button type="button" @click="emit('cancel')">{{ t(`${PREFIX}config.cancel`) }}</button>
        <button type="submit" class="primary">{{ t(`${PREFIX}config.save`) }}</button>
      </div>
    </form>
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
  width: min(520px, calc(100vw - 48px));
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  box-shadow: var(--shadow);
}
h2 {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 600;
}
label {
  display: block;
  margin-top: 12px;
  font-weight: 600;
}
.row {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.hint {
  display: block;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 400;
}
input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
button {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
</style>
