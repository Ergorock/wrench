<script setup lang="ts">
import { Download } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { pushToast } from '../../shell/toasts'
import { useM3 } from './useM3'

const props = defineProps<{
  name: string
  header: string[]
  rows: (string | number)[][]
}>()

const { t } = useI18n()
const m3 = useM3()

async function save(): Promise<void> {
  try {
    const path = await m3.call<string>('save_csv', {
      name: props.name,
      header: props.header,
      rows: props.rows,
    })
    pushToast(t('tools.m3.csv.saved', { path }), 'info')
  } catch {
    // useTool has already shown the error toast.
  }
}
</script>

<template>
  <button type="button" :disabled="rows.length === 0" @click="save">
    <Download :size="15" class="m3-icon" />
    {{ t('tools.m3.csv.export') }}
  </button>
</template>
