<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { TriangleAlert, X } from '@lucide/vue'
import { useShell } from '../state'

const { t } = useI18n()
const { bootstrap } = useShell()
const dismissed = ref<string[]>([])
const visible = computed(() => (bootstrap.value?.warnings ?? []).filter((w) => !dismissed.value.includes(w)))
</script>

<template>
  <div v-for="code in visible" :key="code" class="banner" role="alert">
    <TriangleAlert :size="18" class="icon" />
    <span class="text">{{ t(`warnings.${code}`) }}</span>
    <button type="button" class="close" :title="t('common.close')" :aria-label="t('common.close')" @click="dismissed.push(code)">
      <X :size="16" />
    </button>
  </div>
</template>

<style scoped>
.banner {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 24px 0;
  padding: 10px 12px 10px 16px;
  background: var(--warning-bg);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius);
}
.icon {
  flex: none;
}
.text {
  flex: 1;
  line-height: 1.4;
}
.close {
  display: flex;
  padding: 6px;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--text);
  cursor: pointer;
}
.close:hover {
  background: var(--hover);
}
</style>
