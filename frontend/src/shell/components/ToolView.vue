<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { lucideIcon } from '../icons'
import { useShell } from '../state'
import { toolLoaders } from '../toolComponents'
import HomeView from './HomeView.vue'

// The parent keys this view by tool id, so the props never change for an instance.
const props = defineProps<{ toolId: string }>()

const { t } = useI18n()
const { bootstrap } = useShell()
const icon = computed(() => lucideIcon(bootstrap.value?.tools.find((x) => x.id === props.toolId)?.icon ?? 'box'))
const loader = toolLoaders[props.toolId]
const ToolComponent = loader ? defineAsyncComponent(loader) : null
</script>

<template>
  <HomeView v-if="!ToolComponent" />
  <section v-else class="tool">
    <header class="header">
      <component :is="icon" :size="22" />
      <h1>{{ t(`tools.${toolId}.name`) }}</h1>
    </header>
    <component :is="ToolComponent" />
  </section>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}
</style>
