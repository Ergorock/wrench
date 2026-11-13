<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AppWindow } from '@lucide/vue'
import { appIcon } from '../../shell/appIcons'
import { gitBadges } from './logic'
import type { EditorView, GitView, ProjectEntry } from './types'

const PREFIX = 'tools.projects.'

const props = defineProps<{
  project: ProjectEntry
  git: GitView | undefined
  editors: EditorView[]
  selected: boolean
  /** Shown under the name: the relative path, in search results. */
  showPath: boolean
}>()
const emit = defineEmits<{ select: []; open: [editorId: string] }>()

const { t } = useI18n()
const badges = computed(() => gitBadges(props.git))
const badgeText = (kind: string, n?: number): string => t(`${PREFIX}badges.${kind}`, { n })
const badgeTitle = (kind: string, n?: number): string =>
  kind === 'error' ? (props.git?.error?.message ?? '') : t(`${PREFIX}badges.${kind}Title`, { n })
const nameIcon = computed(() => (props.project.exe ? appIcon(props.project.exe).value : null))
const editorTitle = (e: EditorView): string =>
  t(`${PREFIX}editor.${e.available ? 'open' : 'missing'}`, { name: e.name })
</script>

<template>
  <div class="project-card" :class="{ selected }" :data-project="project.path" @click="emit('select')">
    <div class="name">
      <img v-if="nameIcon" class="name-icon" :src="nameIcon" alt="" />{{ project.name }}
    </div>
    <div v-if="git?.branch" class="branch">{{ git.branch }}</div>
    <div v-if="showPath" class="path">{{ project.rel_path }}</div>
    <div v-if="project.techs.length > 0 || project.is_template" class="techs">
      <span v-if="project.is_template" class="tech template">{{ t(`${PREFIX}card.template`) }}</span>
      <span v-for="tech in project.techs" :key="tech" class="tech">{{ tech }}</span>
    </div>
    <div class="footer">
      <span class="badges">
        <span
          v-for="b in badges"
          :key="b.kind"
          class="badge"
          :class="b.kind"
          :title="badgeTitle(b.kind, b.n)"
        >{{ badgeText(b.kind, b.n) }}</span>
      </span>
      <span class="editors">
        <button
          v-for="e in editors"
          :key="e.id"
          type="button"
          class="editor"
          :title="editorTitle(e)"
          :aria-label="editorTitle(e)"
          :disabled="!e.available"
          @click.stop="emit('open', e.id)"
        >
          <img v-if="appIcon(e.exe).value" :src="appIcon(e.exe).value ?? ''" alt="" />
          <AppWindow v-else :size="16" aria-hidden="true" />
        </button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.project-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  cursor: pointer;
}
.project-card:hover {
  background: var(--hover);
}
.project-card.selected {
  border-color: var(--accent);
}
.name {
  font-weight: 600;
  overflow-wrap: anywhere;
}
.name-icon {
  width: 16px;
  height: 16px;
  margin-right: 6px;
  vertical-align: text-bottom;
}
.branch,
.path {
  color: var(--text-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.techs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tech {
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--active);
  font-size: 11px;
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
}
.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.badge {
  font-size: 12px;
  color: var(--text-muted);
}
.badge.conflict,
.badge.error {
  color: var(--danger);
}
.badge.ahead,
.badge.changes {
  color: var(--accent);
}
.editors {
  display: flex;
  gap: 4px;
}
.editor {
  display: inline-flex;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
}
.editor:hover:not(:disabled) {
  background: var(--hover);
}
.editor:disabled {
  opacity: 0.4;
  cursor: default;
}
.editor img {
  width: 16px;
  height: 16px;
}
</style>
