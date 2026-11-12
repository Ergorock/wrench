<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Wrench } from '@lucide/vue'
import { useShell } from '../state'

const { t } = useI18n()
const { view } = useShell()

function showSettings(): void {
  view.value = 'settings'
}
</script>

<template>
  <section class="home">
    <Wrench :size="48" class="logo" />
    <h1>{{ t('home.title') }}</h1>
    <p>{{ t('home.body') }}</p>
    <button type="button" class="primary" @click="showSettings">{{ t('home.openSettings') }}</button>
  </section>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 100%;
  max-width: 520px;
  margin: 0 auto;
  text-align: center;
}
.logo {
  color: var(--accent);
}
h1 {
  margin: 8px 0 0;
  font-size: 24px;
  font-weight: 600;
}
p {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}
.primary {
  margin-top: 12px;
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius);
  background: var(--accent);
  color: var(--accent-text);
  font: inherit;
  cursor: pointer;
}
.primary:hover {
  filter: brightness(1.08);
}
</style>
