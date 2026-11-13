<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'

const PREFIX = 'tools.dev_tools.encode.'
const { t } = useI18n()
const tool = useTool('dev_tools')

const SCHEMES = ['base64', 'url'] as const
const scheme = ref<(typeof SCHEMES)[number]>('base64')
const input = ref('')
const output = ref('')

async function run(direction: 'encode' | 'decode'): Promise<void> {
  try {
    output.value = await tool.call<string>(`${direction}_${scheme.value}`, { text: input.value })
  } catch {
    // useTool has already shown the error toast.
    output.value = ''
  }
}
</script>

<template>
  <div class="panel">
    <div class="radio-group" role="radiogroup">
      <label v-for="s in SCHEMES" :key="s" class="radio">
        <input v-model="scheme" type="radio" name="dev-tools-scheme" :value="s" />
        {{ t(`${PREFIX}schemes.${s}`) }}
      </label>
    </div>

    <label class="field-label" for="dev-tools-encode-input">{{ t(`${PREFIX}input`) }}</label>
    <textarea id="dev-tools-encode-input" v-model="input" rows="6" class="mono" />

    <div class="actions">
      <button type="button" class="primary" @click="run('encode')">{{ t(`${PREFIX}encode`) }}</button>
      <button type="button" @click="run('decode')">{{ t(`${PREFIX}decode`) }}</button>
    </div>

    <label class="field-label" for="dev-tools-encode-output">{{ t(`${PREFIX}output`) }}</label>
    <textarea id="dev-tools-encode-output" :value="output" rows="6" class="mono" readonly />
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.radio-group {
  display: flex;
  gap: 16px;
}

.radio {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.field-label {
  color: var(--text-muted);
  font-size: 12px;
}

textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 8px;
  resize: vertical;
  background: var(--bg-elevated);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font: inherit;
}

.mono {
  font-family: Consolas, 'Cascadia Mono', monospace;
}

.actions {
  display: flex;
  gap: 8px;
}

button {
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}

button:hover {
  background: var(--hover);
}

button.primary {
  background: var(--accent);
  color: var(--accent-text);
  border-color: var(--accent);
}
</style>
