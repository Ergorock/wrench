<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'

const props = defineProps<{ kind: 'json' | 'xml' }>()

const PREFIX = 'tools.dev_tools.format.'
const { t } = useI18n()
const tool = useTool('dev_tools')

const input = ref('')
const output = ref('')

async function run(minify = false): Promise<void> {
  try {
    output.value =
      props.kind === 'json'
        ? await tool.call<string>('format_json', { text: input.value, minify })
        : await tool.call<string>('format_xml', { text: input.value })
  } catch {
    // useTool has already shown the error toast.
    output.value = ''
  }
}
</script>

<template>
  <div class="panel">
    <label class="field-label" :for="`dev-tools-${kind}-input`">{{ t(`${PREFIX}input`) }}</label>
    <textarea :id="`dev-tools-${kind}-input`" v-model="input" rows="10" class="mono" spellcheck="false" />

    <div class="actions">
      <button type="button" class="primary" @click="run(false)">{{ t(`${PREFIX}format`) }}</button>
      <button v-if="kind === 'json'" type="button" @click="run(true)">{{ t(`${PREFIX}minify`) }}</button>
    </div>

    <label class="field-label" :for="`dev-tools-${kind}-output`">{{ t(`${PREFIX}output`) }}</label>
    <textarea :id="`dev-tools-${kind}-output`" :value="output" rows="10" class="mono" readonly />
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
