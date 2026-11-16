<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import JobPanel from './JobPanel.vue'
import SessionBar from './SessionBar.vue'
import { countEdas } from './logic'
import { useM3 } from './useM3'

const PREFIX = 'tools.m3.eda.'
const { t } = useI18n()
const m3 = useM3()

const edas = ref('')
const count = computed(() => countEdas(edas.value))
const busy = computed(() => m3.state.value?.job.running === true)
const connected = computed(() => m3.state.value?.connected.eda === true)

async function save(): Promise<void> {
  try {
    await m3.saveConfig()
  } catch {
    // useTool has already shown the error toast.
  }
}

async function run(): Promise<void> {
  try {
    await m3.call('eda_export', { edas: edas.value })
  } catch {
    // useTool has already shown the error toast.
  }
}
</script>

<template>
  <div class="m3-panel">
    <div class="m3-row">
      <label class="m3-field url">
        {{ t(`${PREFIX}baseUrl`) }}
        <input v-model="m3.config.value.eda_base_url" type="text" spellcheck="false" @change="save" />
      </label>
      <label class="m3-field short">
        {{ t(`${PREFIX}company`) }}
        <input v-model="m3.config.value.company" type="text" @change="save" />
      </label>
      <label class="m3-field short">
        {{ t(`${PREFIX}division`) }}
        <input v-model="m3.config.value.division" type="text" @change="save" />
      </label>
      <label class="m3-field short">
        {{ t(`${PREFIX}language`) }}
        <input v-model="m3.config.value.language" type="text" @change="save" />
      </label>
    </div>

    <SessionBar target="eda" />

    <label class="m3-field">
      {{ t(`${PREFIX}list`) }}
      <textarea v-model="edas" rows="8" spellcheck="false" :placeholder="t(`${PREFIX}placeholder`)" />
    </label>

    <div class="m3-row">
      <button type="button" class="primary" :disabled="busy || !connected || count === 0" @click="run">
        {{ t(`${PREFIX}export`, { count }) }}
      </button>
      <span class="m3-muted">{{ t(`${PREFIX}target`, { dir: m3.config.value.output_dir }) }}</span>
    </div>

    <JobPanel :kinds="['eda_export']" />
  </div>
</template>

<style scoped>
.url {
  flex: 1;
  min-width: 220px;
}

.short input {
  width: 80px;
}
</style>
