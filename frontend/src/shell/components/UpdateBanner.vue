<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, X } from '@lucide/vue'
import { BridgeError, openUrl } from '../../bridge/client'
import { errorMessage, toastError } from '../toasts'
import { useUpdates } from '../updates'

const { t } = useI18n()
const { status, bannerVisible, install, dismiss } = useUpdates()

const percent = computed(() => Math.round(Math.min(1, Math.max(0, status.value.progress)) * 100))
const errorText = computed(() =>
  errorMessage(new BridgeError(status.value.error_code ?? 'generic', '')),
)

async function openNotes(): Promise<void> {
  const url = status.value.info?.notes_url
  if (!url) return
  try {
    await openUrl(url)
  } catch (err) {
    toastError(err)
  }
}
</script>

<template>
  <div v-if="bannerVisible" class="banner" role="status">
    <Download :size="18" class="icon" />
    <div class="body">
      <template v-if="status.status === 'available'">
        <span class="text">{{ t('updates.available', { version: status.info?.version ?? '' }) }}</span>
      </template>
      <template v-else-if="status.status === 'downloading'">
        <span class="text">{{ t('updates.downloading', { percent }) }}</span>
        <div
          class="bar"
          role="progressbar"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="percent"
          :aria-label="t('updates.downloading', { percent })"
        >
          <div class="fill" :style="{ width: `${percent}%` }" />
        </div>
      </template>
      <template v-else-if="status.status === 'installing'">
        <span class="text">{{ t('updates.installing') }}</span>
      </template>
      <template v-else>
        <span class="text" role="alert">{{ errorText }}</span>
      </template>
    </div>
    <div v-if="status.status === 'available'" class="actions">
      <button type="button" class="btn primary" @click="install()">{{ t('updates.install') }}</button>
      <button type="button" class="btn" @click="openNotes">{{ t('updates.notes') }}</button>
      <button type="button" class="btn" @click="dismiss()">{{ t('updates.later') }}</button>
    </div>
    <div v-else-if="status.status === 'error'" class="actions">
      <button type="button" class="btn primary" @click="install()">{{ t('updates.retry') }}</button>
    </div>
    <button
      v-if="status.status === 'error'"
      type="button"
      class="close"
      :title="t('common.close')"
      :aria-label="t('common.close')"
      @click="dismiss()"
    >
      <X :size="16" />
    </button>
  </div>
</template>

<style scoped>
.banner {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 24px 0;
  padding: 10px 12px 10px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
}
.icon {
  flex: none;
}
.body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.text {
  line-height: 1.4;
}
.bar {
  height: 6px;
  border-radius: 3px;
  background: var(--border);
  overflow: hidden;
}
.fill {
  height: 100%;
  background: var(--accent);
  transition: width 200ms ease;
}
.actions {
  display: flex;
  gap: 8px;
  flex: none;
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
.btn:hover {
  background: var(--hover);
}
.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
.btn.primary:hover {
  background: var(--accent);
  opacity: 0.9;
}
.close {
  display: flex;
  padding: 6px;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--text);
  cursor: pointer;
}
.close:hover {
  background: var(--hover);
}
</style>
