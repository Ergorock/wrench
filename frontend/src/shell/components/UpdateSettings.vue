<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { BridgeError } from '../../bridge/client'
import { useShell } from '../state'
import { errorMessage } from '../toasts'
import { useUpdates } from '../updates'

const { t } = useI18n()
const { settings, update } = useShell()
const { status, checkNow, install } = useUpdates()

const supported = computed(() => status.value.supported)
const checking = ref(false)
// A result is shown only after the user asked for a check.
const checked = ref(false)

const resultError = computed(() => errorMessage(new BridgeError(status.value.error_code ?? 'generic', '')))
const busy = computed(() => status.value.status === 'downloading' || status.value.status === 'installing')

async function onCheck(): Promise<void> {
  checking.value = true
  try {
    await checkNow()
    checked.value = true
  } finally {
    checking.value = false
  }
}

function onAutoCheck(e: Event): void {
  const on = (e.target as HTMLInputElement).checked
  void update((s) => {
    s.updates.auto_check = on
  })
}
</script>

<template>
  <div class="card" :class="{ unsupported: !supported }" :aria-disabled="!supported">
    <span class="card-title">{{ t('updates.sectionTitle') }}</span>
    <span class="hint">{{ t('updates.currentVersion', { version: status.current_version }) }}</span>
    <label class="check" :class="{ disabled: !supported }">
      <input
        type="checkbox"
        :checked="settings.updates.auto_check"
        :disabled="!supported"
        @change="onAutoCheck"
      />
      <span>{{ t('updates.autoCheck') }}</span>
    </label>
    <div class="row">
      <button type="button" class="btn" :disabled="!supported || checking || busy" @click="onCheck">
        {{ t('updates.checkNow') }}
      </button>
      <span v-if="supported && checked" class="result" role="status">
        <template v-if="status.status === 'up_to_date'">{{ t('updates.upToDate') }}</template>
        <template v-else-if="status.status === 'available'">
          {{ t('updates.available', { version: status.info?.version ?? '' }) }}
          <button type="button" class="btn primary" @click="install()">{{ t('updates.install') }}</button>
        </template>
        <template v-else-if="status.status === 'error'">{{ resultError }}</template>
      </span>
    </div>
    <p v-if="!supported" class="hint">{{ t('updates.unsupported') }}</p>
  </div>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.card.unsupported {
  opacity: 0.6;
}
.card-title {
  font-weight: 600;
}
.hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.4;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.check.disabled {
  color: var(--text-muted);
  cursor: default;
}
.check input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--accent);
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.result {
  display: flex;
  align-items: center;
  gap: 10px;
}
.btn {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.btn:hover:not(:disabled) {
  background: var(--hover);
}
.btn:disabled {
  color: var(--text-muted);
  cursor: default;
}
.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
</style>
