<script setup lang="ts">
import type { Component } from 'vue'
import { Star } from '@lucide/vue'

defineProps<{
  icon: Component
  label: string
  collapsed: boolean
  active?: boolean
  highlighted?: boolean
  /** Shows a favorite toggle; `starred` tells whether the tool is already a favorite. */
  starLabel?: string
  starred?: boolean
}>()
defineEmits<{ star: [] }>()
</script>

<template>
  <div class="row" :class="{ starred }">
    <button
      type="button"
      class="item"
      :class="{ active, highlighted }"
      :title="collapsed ? label : undefined"
      :aria-label="collapsed ? label : undefined"
      :aria-current="active ? 'page' : undefined"
    >
      <component :is="icon" :size="18" class="icon" />
      <span v-if="!collapsed" class="label">{{ label }}</span>
    </button>
    <button
      v-if="starLabel && !collapsed"
      type="button"
      class="star"
      :title="starLabel"
      :aria-label="starLabel"
      :aria-pressed="starred"
      @click.stop="$emit('star')"
    >
      <Star :size="14" :fill="starred ? 'currentColor' : 'none'" />
    </button>
  </div>
</template>

<style scoped>
.row {
  position: relative;
}
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
.row:hover .item,
.item.highlighted {
  background: var(--hover);
}
.item.active {
  background: var(--active);
  font-weight: 600;
}
.item.active .icon {
  color: var(--accent);
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
  padding-right: 24px;
}
.star {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
}
.row:hover .star,
.star:focus-visible,
.row.starred .star {
  opacity: 1;
}
.row.starred .star {
  color: var(--accent);
}
.star:hover {
  background: var(--active);
}
</style>
