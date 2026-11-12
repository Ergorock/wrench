<script setup lang="ts">
import { useShell } from '../state'
import HomeView from './HomeView.vue'
import SettingsView from './SettingsView.vue'
import Sidebar from './Sidebar.vue'
import ToastHost from './ToastHost.vue'
import ToolView from './ToolView.vue'
import WarningBanner from './WarningBanner.vue'

const { view } = useShell()
</script>

<template>
  <div class="layout">
    <Sidebar />
    <main class="main">
      <WarningBanner />
      <div class="content">
        <HomeView v-if="view === 'home'" />
        <SettingsView v-else-if="view === 'settings'" />
        <ToolView v-else :key="view" :tool-id="view" />
      </div>
    </main>
    <ToastHost />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.content {
  flex: 1;
  overflow: auto;
  padding: 28px 32px;
}
</style>
