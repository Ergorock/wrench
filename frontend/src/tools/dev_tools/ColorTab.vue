<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import type { ColorInfo } from './types'

const PREFIX = 'tools.dev_tools.color.'
const { t } = useI18n()
const tool = useTool('dev_tools')

const hexText = ref('#1E90FF')
const info = ref<ColorInfo | null>(null)

const pickerValue = computed(() => info.value?.hex.toLowerCase() ?? '#000000')
const hslText = computed(() => {
  const [h, s, l] = info.value?.hsl ?? [0, 0, 0]
  return `hsl(${h}, ${s}%, ${l}%)`
})
const rgbText = computed(() => {
  const [r, g, b] = info.value?.rgb ?? [0, 0, 0]
  return `rgb(${r}, ${g}, ${b})`
})

async function convert(color: string): Promise<void> {
  try {
    info.value = await tool.call<ColorInfo>('convert_color', { color })
    hexText.value = info.value.hex
  } catch {
    // useTool has already shown the error toast; the last valid color stays displayed.
  }
}

onMounted(() => {
  void convert(hexText.value)
})
</script>

<template>
  <div class="panel">
    <div class="row">
      <input
        type="color"
        class="picker"
        :value="pickerValue"
        :aria-label="t(`${PREFIX}picker`)"
        :title="t(`${PREFIX}picker`)"
        @input="convert(($event.target as HTMLInputElement).value)"
      />
      <div class="swatch" :style="{ background: info?.hex ?? 'transparent' }" />
      <div class="field">
        <label class="field-label" for="dev-tools-color-hex">{{ t(`${PREFIX}hex`) }}</label>
        <input
          id="dev-tools-color-hex"
          v-model="hexText"
          type="text"
          class="mono"
          spellcheck="false"
          @change="convert(hexText)"
        />
      </div>
    </div>

    <dl v-if="info" class="values">
      <dt>{{ t(`${PREFIX}hex`) }}</dt>
      <dd class="mono">{{ info.hex }}</dd>
      <dt>{{ t(`${PREFIX}rgb`) }}</dt>
      <dd class="mono">{{ rgbText }}</dd>
      <dt>{{ t(`${PREFIX}hsl`) }}</dt>
      <dd class="mono">{{ hslText }}</dd>
    </dl>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}

.picker {
  width: 56px;
  height: 40px;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  cursor: pointer;
}

.swatch {
  width: 120px;
  height: 40px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  color: var(--text-muted);
  font-size: 12px;
}

input[type='text'] {
  width: 140px;
  padding: 6px 8px;
  background: var(--bg-elevated);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font: inherit;
}

.mono {
  font-family: Consolas, 'Cascadia Mono', monospace;
}

.values {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 16px;
  margin: 0;
}

.values dt {
  color: var(--text-muted);
}

.values dd {
  margin: 0;
}
</style>
