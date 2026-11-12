<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RepoView } from './types'

const PREFIX = 'tools.git_repos.'

const props = defineProps<{ repo: RepoView; canPush: boolean }>()
const emit = defineEmits<{ close: []; submit: [message: string, push: boolean] }>()

const { t } = useI18n()
const message = ref('')
const input = ref<HTMLTextAreaElement | null>(null)
const valid = computed(() => message.value.trim() !== '')
const count = computed(() => props.repo.changed_files.length)

function submit(push: boolean): void {
  if (valid.value) emit('submit', message.value, push)
}

onMounted(() => input.value?.focus())
</script>

<template>
  <div class="overlay" @click.self="emit('close')" @keydown.esc="emit('close')">
    <form class="dialog" role="dialog" aria-modal="true" @submit.prevent="submit(false)">
      <h2>{{ t(`${PREFIX}commit.title`, { name: repo.name }) }}</h2>
      <p class="summary">{{ t(`${PREFIX}commit.summary`, { n: count }, count) }}</p>
      <details v-if="count > 0">
        <summary>{{ t(`${PREFIX}commit.files`) }}</summary>
        <ul class="files">
          <li v-for="file in repo.changed_files" :key="file">{{ file }}</li>
        </ul>
      </details>
      <label class="label" for="git-repos-commit-message">{{ t(`${PREFIX}commit.message`) }}</label>
      <textarea
        id="git-repos-commit-message"
        ref="input"
        v-model="message"
        rows="3"
        required
        :placeholder="t(`${PREFIX}commit.placeholder`)"
        @keydown.ctrl.enter.prevent="submit(false)"
      />
      <div class="buttons">
        <button type="button" @click="emit('close')">{{ t(`${PREFIX}commit.cancel`) }}</button>
        <button type="submit" :disabled="!valid">{{ t(`${PREFIX}commit.commit`) }}</button>
        <button v-if="canPush" type="button" class="primary" :disabled="!valid" @click="submit(true)">
          {{ t(`${PREFIX}commit.commitAndPush`) }}
        </button>
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
.summary {
  margin: 0 0 8px;
  color: var(--text-muted);
}
.files {
  max-height: 160px;
  overflow: auto;
  margin: 6px 0 0;
  padding-left: 18px;
  font-family: Consolas, monospace;
  font-size: 12px;
}
.label {
  display: block;
  margin: 12px 0 4px;
  font-weight: 600;
}
textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  resize: vertical;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
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
button:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
