<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pin, PinOff } from '@lucide/vue'
import { useShell } from '../state'

const props = defineProps<{ x: number; y: number; toolId: string }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const { settings, toggleFavorite } = useShell()
const root = ref<HTMLElement | null>(null)
const pinned = computed(() => settings.value.sidebar.favorites.includes(props.toolId))

function choose(): void {
  toggleFavorite(props.toolId)
  emit('close')
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape') emit('close')
}

function onPointer(e: MouseEvent): void {
  if (!root.value?.contains(e.target as Node)) emit('close')
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('mousedown', onPointer)
  root.value?.querySelector('button')?.focus()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('mousedown', onPointer)
})
</script>

<template>
  <div ref="root" class="menu" role="menu" :style="{ left: `${x}px`, top: `${y}px` }">
    <button type="button" role="menuitem" class="entry" @click="choose">
      <component :is="pinned ? PinOff : Pin" :size="16" />
      <span>{{ t(pinned ? 'nav.unpin' : 'nav.pin') }}</span>
    </button>
  </div>
</template>

<style scoped>
.menu {
  position: fixed;
  z-index: 20;
  min-width: 200px;
  padding: 4px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.entry {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.entry:hover,
.entry:focus-visible {
  background: var(--hover);
  outline: none;
}
</style>
