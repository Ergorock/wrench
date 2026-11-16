<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useM3 } from './useM3'

const props = defineProps<{ kinds: string[] }>()

const PREFIX = 'tools.m3.'
const { t } = useI18n()
const m3 = useM3()

const job = computed(() => {
  const j = m3.state.value?.job
  return j && j.kind !== null && props.kinds.includes(j.kind) ? j : null
})

async function cancel(): Promise<void> {
  await m3.call('cancel')
}
</script>

<template>
  <div v-if="job" class="m3-panel job">
    <div class="m3-row">
      <span>{{ t(`${PREFIX}status.${job.status || 'starting'}`) }}</span>
      <span class="m3-muted">
        {{ t(`${PREFIX}job.counts`, { done: job.done, total: job.total, ok: job.ok, failed: job.failed }) }}
      </span>
      <button v-if="job.running" type="button" @click="cancel">{{ t(`${PREFIX}cancel`) }}</button>
    </div>
    <progress class="m3-progress" :max="Math.max(job.total, 1)" :value="job.done" />
    <pre v-if="job.log.length > 0" class="m3-log">{{ job.log.join('\n') }}</pre>
  </div>
</template>
