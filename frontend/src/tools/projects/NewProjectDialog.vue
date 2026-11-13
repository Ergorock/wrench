<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTool } from '../../bridge/useTool'
import { isRemoteUrl } from './logic'

const PREFIX = 'tools.projects.new.'

const props = defineProps<{ destination: string; busy: boolean; gitAvailable: boolean }>()
const emit = defineEmits<{ submit: [template: string, name: string, remoteUrl: string | null]; cancel: [] }>()

const { t } = useI18n()
const tool = useTool('projects')
const templates = ref<string[]>([])
const template = ref('')
const name = ref('')
const url = ref('')
const input = ref<HTMLInputElement | null>(null)

const cleanName = computed(() => name.value.trim())
const cleanUrl = computed(() => url.value.trim())
const valid = computed(
  () => template.value !== '' && cleanName.value !== '' && (cleanUrl.value === '' || isRemoteUrl(cleanUrl.value)),
)

function submit(): void {
  if (valid.value && !props.busy) emit('submit', template.value, cleanName.value, cleanUrl.value || null)
}

onMounted(async () => {
  input.value?.focus()
  try {
    templates.value = await tool.call<string[]>('list_templates')
    template.value = templates.value[0] ?? ''
  } catch {
    // useTool has already shown the error toast.
  }
})
</script>

<template>
  <div class="overlay" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
    <form class="dialog" role="dialog" aria-modal="true" @submit.prevent="submit">
      <h2>{{ t(`${PREFIX}title`) }}</h2>
      <fieldset>
        <legend>{{ t(`${PREFIX}template`) }}</legend>
        <p v-if="templates.length === 0" class="hint">{{ t(`${PREFIX}noTemplates`) }}</p>
        <label v-for="tpl in templates" :key="tpl" class="radio">
          <input v-model="template" type="radio" name="projects-new-template" :value="tpl" />
          {{ tpl }}
        </label>
      </fieldset>
      <label for="projects-new-name">{{ t(`${PREFIX}name`) }}</label>
      <input id="projects-new-name" ref="input" v-model="name" type="text" />
      <label for="projects-new-url">{{ t(`${PREFIX}url`) }}</label>
      <input id="projects-new-url" v-model="url" type="text" placeholder="https://github.com/…" />
      <label for="projects-new-destination">{{ t(`${PREFIX}destination`) }}</label>
      <input id="projects-new-destination" data-slot="destination" :value="destination" type="text" readonly />
      <p v-if="!gitAvailable" class="hint">{{ t(`${PREFIX}noGit`) }}</p>
      <div class="buttons">
        <button type="button" @click="emit('cancel')">{{ t(`${PREFIX}cancel`) }}</button>
        <button type="submit" class="primary" :disabled="!valid || busy">
          {{ t(`${PREFIX}${busy ? 'creating' : 'create'}`) }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--active);
  z-index: 50;
}
.dialog {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(460px, calc(100vw - 48px));
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  box-shadow: var(--shadow);
}
h2 {
  margin: 0;
  font-size: 16px;
}
fieldset {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.radio {
  display: flex;
  align-items: center;
  gap: 6px;
}
.hint {
  margin: 0;
  color: var(--text-muted);
}
input[type='text'] {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
input[readonly] {
  color: var(--text-muted);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}
button {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-text);
}
</style>
