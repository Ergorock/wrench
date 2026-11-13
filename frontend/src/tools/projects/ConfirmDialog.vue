<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const PREFIX = 'tools.projects.'

defineProps<{ message: string }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const { t } = useI18n()
const ok = ref<HTMLButtonElement | null>(null)
onMounted(() => ok.value?.focus())
</script>

<template>
  <div class="overlay" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
    <div class="dialog" role="dialog" aria-modal="true">
      <p>{{ message }}</p>
      <div class="buttons">
        <button type="button" @click="emit('cancel')">{{ t(`${PREFIX}confirm.cancel`) }}</button>
        <button ref="ok" type="button" class="primary" @click="emit('confirm')">
          {{ t(`${PREFIX}confirm.confirm`) }}
        </button>
      </div>
    </div>
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
  width: min(420px, calc(100vw - 48px));
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  box-shadow: var(--shadow);
}
p {
  margin: 0 0 14px;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
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
