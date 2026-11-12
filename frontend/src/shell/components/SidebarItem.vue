<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ icon: Component; label: string; collapsed: boolean; active?: boolean }>()
</script>

<template>
  <button
    type="button"
    class="item"
    :class="{ active }"
    :title="collapsed ? label : undefined"
    :aria-label="collapsed ? label : undefined"
    :aria-current="active ? 'page' : undefined"
  >
    <component :is="icon" :size="18" class="icon" />
    <span v-if="!collapsed" class="label">{{ label }}</span>
  </button>
</template>

<style scoped>
.item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  height: 36px;
  padding: 0 10px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
  position: relative;
}
.item:hover {
  background: var(--hover);
}
.item.active {
  background: var(--active);
}
.item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 2px;
  background: var(--accent);
}
.icon {
  flex: none;
}
.label {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
