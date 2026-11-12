<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import HomeView from './HomeView.vue'

const { t } = useI18n()
</script>

<template>
  <div class="load-error">
    <p role="alert" class="message">{{ t('errors.toolLoadFailed') }}</p>
    <HomeView />
  </div>
</template>

<style scoped>
.message {
  margin: 0 0 12px;
  padding: 10px 14px;
  border: 1px solid var(--warning-border);
  border-radius: var(--radius);
  background: var(--warning-bg);
  color: var(--text);
}
</style>
