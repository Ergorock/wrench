<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import { pickFolder } from '../../bridge/client'
import type { Exported, Picture, Code, SymbolKind } from './types'

const PREFIX = 'tools.qr_barcode.'
const BARCODE_TYPES = ['code128', 'code39', 'ean13'] as const
const DEBOUNCE_MS = 400

const { t } = useI18n()
const tool = useTool('qr_barcode')

const kind = ref<SymbolKind>('qr')
const data = ref('')
const barcodeType = ref<(typeof BARCODE_TYPES)[number]>('code128')
const fileName = ref('')
const picture = ref<string | null>(null)
const message = ref<string | null>(null)

const symbol = computed<Code>(() => ({
  kind: kind.value,
  data: data.value,
  barcode_type: barcodeType.value,
}))

const previewSrc = computed(() =>
  picture.value === null ? null : `data:image/svg+xml;charset=utf-8,${encodeURIComponent(picture.value)}`,
)

let seq = 0
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  symbol,
  () => {
    clearTimeout(timer)
    message.value = null
    if (data.value === '') {
      picture.value = null
      return
    }
    timer = setTimeout(() => void generate(), DEBOUNCE_MS)
  },
  { deep: true },
)

async function generate(): Promise<void> {
  const current = ++seq
  try {
    const result = await tool.call<Picture>('generate', { symbol: symbol.value })
    if (current === seq) picture.value = result.svg
  } catch {
    // useTool has already shown the error toast.
    if (current === seq) picture.value = null
  }
}

async function exportSvg(): Promise<void> {
  const folder = await pickFolder()
  if (folder === null) return
  try {
    const saved = await tool.call<Exported>('export', {
      symbol: symbol.value,
      folder,
      name: fileName.value.trim() || t(`${PREFIX}fileNameDefault`),
    })
    message.value = t(`${PREFIX}exported`, { path: saved.path })
  } catch {
    // useTool has already shown the error toast.
  }
}
</script>

<template>
  <div class="qr">
    <div class="line">
      <fieldset class="choice">
        <legend>{{ t(`${PREFIX}kind`) }}</legend>
        <label><input v-model="kind" type="radio" value="qr" /> {{ t(`${PREFIX}qr`) }}</label>
        <label><input v-model="kind" type="radio" value="barcode" /> {{ t(`${PREFIX}barcode`) }}</label>
      </fieldset>
      <label v-if="kind === 'barcode'" class="field">
        <span>{{ t(`${PREFIX}barcodeType`) }}</span>
        <select v-model="barcodeType">
          <option v-for="type in BARCODE_TYPES" :key="type" :value="type">
            {{ t(`${PREFIX}barcodeTypes.${type}`) }}
          </option>
        </select>
      </label>
    </div>

    <label class="field">
      <span>{{ t(`${PREFIX}data`) }}</span>
      <input v-model="data" :placeholder="t(`${PREFIX}dataPlaceholder`)" maxlength="1000" />
    </label>

    <section class="panel preview">
      <h2>{{ t(`${PREFIX}preview`) }}</h2>
      <img v-if="previewSrc" :src="previewSrc" :alt="data" class="image" />
      <p v-else class="hint">{{ t(`${PREFIX}noPreview`) }}</p>
    </section>

    <div class="line">
      <label class="field">
        <span>{{ t(`${PREFIX}fileName`) }}</span>
        <input v-model="fileName" :placeholder="t(`${PREFIX}fileNameDefault`)" maxlength="60" />
      </label>
      <button type="button" class="button primary" :disabled="!previewSrc" @click="exportSvg">
        {{ t(`${PREFIX}export`) }}
      </button>
    </div>
    <p v-if="message" class="message" role="status">{{ message }}</p>
  </div>
</template>

<style scoped>
.qr {
  max-width: 680px;
}
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 14px;
}
.choice {
  display: flex;
  gap: 16px;
  align-items: center;
  margin: 0;
  padding: 0;
  border: none;
  color: var(--text);
}
.choice legend {
  font-size: 13px;
  color: var(--text-muted);
  padding: 0;
  margin-bottom: 4px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 160px;
  font-size: 13px;
  color: var(--text-muted);
}
input,
select {
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.button {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--active);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.button.primary {
  background: var(--accent);
  color: var(--accent-text);
  border-color: transparent;
}
.button:disabled {
  opacity: 0.5;
  cursor: default;
}
.button:focus-visible,
input:focus-visible,
select:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.panel {
  margin-bottom: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.preview h2 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.image {
  display: block;
  max-width: 100%;
  max-height: 320px;
  margin: 0 auto;
  background: #fff;
  border-radius: 6px;
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}
.message {
  margin: 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}
</style>
