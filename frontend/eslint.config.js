import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'

export default defineConfigWithVueTs(
  { ignores: ['dist/**', 'node_modules/**'] },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  // Sidebar.vue is the name the plan fixes for the shell's sidebar.
  { rules: { 'vue/multi-word-component-names': ['error', { ignores: ['Sidebar'] }] } },
)
