<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from './shell/components/AppLayout.vue'
import { useShell } from './shell/state'

const { t } = useI18n()
const { bootstrap, init } = useShell()
const failed = ref(false)

onMounted(() => {
  init().catch(() => {
    failed.value = true
  })
})
</script>

<template>
  <p v-if="failed" class="failed">{{ t('errors.generic') }}</p>
  <AppLayout v-else-if="bootstrap" />
</template>

<style scoped>
.failed {
  margin: 32px;
}
</style>
