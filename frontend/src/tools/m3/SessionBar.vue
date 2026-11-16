<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useM3 } from './useM3'
import type { Target } from './types'

const props = defineProps<{ target: Target }>()

const PREFIX = 'tools.m3.'
const { t } = useI18n()
const m3 = useM3()

const job = computed(() => m3.state.value?.job)
const connected = computed(() => m3.state.value?.connected[props.target] ?? false)
const loggingIn = computed(() => job.value?.running === true && job.value.kind === `login_${props.target}`)
const busy = computed(() => job.value?.running === true)

async function login(): Promise<void> {
  try {
    await m3.call('login', { target: props.target })
  } catch {
    // useTool has already shown the error toast.
  }
}

async function cancel(): Promise<void> {
  await m3.call('cancel')
}
</script>

<template>
  <div class="m3-row">
    <span class="m3-badge" :class="{ on: connected }">
      {{ t(`${PREFIX}${connected ? 'session.connected' : 'session.disconnected'}`) }}
    </span>
    <button type="button" class="primary" :disabled="busy" @click="login">
      {{ t(`${PREFIX}${connected ? 'session.reconnect' : 'session.connect'}`) }}
    </button>
    <template v-if="loggingIn">
      <span class="m3-muted">{{ t(`${PREFIX}status.${job?.status || 'starting'}`) }}</span>
      <button type="button" @click="cancel">{{ t(`${PREFIX}cancel`) }}</button>
    </template>
    <span v-else class="m3-muted">{{ t(`${PREFIX}session.hint.${target}`) }}</span>
  </div>
</template>
