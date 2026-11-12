<script setup lang="ts">
defineProps<{ label: string }>()
</script>

<template>
  <kbd class="keycap">{{ label }}</kbd>
</template>

<style scoped>
.keycap {
  display: inline-block;
  min-width: 22px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 6px;
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
  white-space: nowrap;
}
</style>
