<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import HomeView from './HomeView.vue'

const emit = defineEmits<{ retry: [] }>()
const { t } = useI18n()
</script>

<template>
  <div class="load-error">
    <div role="alert" class="message">
      <span>{{ t('errors.toolLoadFailed') }}</span>
      <button type="button" class="retry" @click="emit('retry')">{{ t('errors.toolLoadRetry') }}</button>
    </div>
    <HomeView />
  </div>
</template>

<style scoped>
.message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 12px;
  padding: 10px 14px;
  border: 1px solid var(--warning-border);
  border-radius: var(--radius);
  background: var(--warning-bg);
  color: var(--text);
}
.retry {
  padding: 4px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.retry:hover {
  background: var(--hover);
}
.retry:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
</style>
