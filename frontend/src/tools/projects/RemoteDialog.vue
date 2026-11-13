<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const PREFIX = 'tools.projects.panel.remote.'

const emit = defineEmits<{ submit: [url: string]; cancel: [] }>()

const { t } = useI18n()
const url = ref('')
const input = ref<HTMLInputElement | null>(null)
const valid = computed(() => url.value.trim() !== '')

function submit(): void {
  if (valid.value) emit('submit', url.value.trim())
}

onMounted(() => input.value?.focus())
</script>

<template>
  <div class="overlay" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
    <form class="dialog" role="dialog" aria-modal="true" @submit.prevent="submit">
      <h2>{{ t(`${PREFIX}title`) }}</h2>
      <label for="projects-remote-url">{{ t(`${PREFIX}url`) }}</label>
      <input id="projects-remote-url" ref="input" v-model="url" type="text" placeholder="https://github.com/…" />
      <div class="buttons">
        <button type="button" @click="emit('cancel')">{{ t(`${PREFIX}cancel`) }}</button>
        <button type="submit" class="primary" :disabled="!valid">{{ t(`${PREFIX}save`) }}</button>
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
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(420px, calc(100vw - 48px));
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  box-shadow: var(--shadow);
}
h2 {
  margin: 0;
  font-size: 16px;
}
input {
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
  margin-top: 6px;
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
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
</style>
