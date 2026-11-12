<script setup lang="ts">
import { toasts } from '../toasts'
</script>

<template>
  <div class="host" aria-live="polite">
    <div v-for="toast in toasts" :key="toast.id" class="toast" :class="toast.kind">{{ toast.message }}</div>
  </div>
</template>

<style scoped>
.host {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 360px;
}
.toast {
  padding: 12px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  line-height: 1.4;
}
.toast.error {
  border-left-color: var(--danger);
}
</style>
