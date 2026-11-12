import type { Component } from 'vue'
import { Box, Code, Folder, Keyboard, Monitor, Zap } from '@lucide/vue'

/**
 * Icons that can be looked up by name (category icons from `core/categories.py`, `MANIFEST.icon`
 * of tools). Explicit named imports keep the bundle tree-shaken. To use a new icon in a manifest
 * or category, add it here: backend/tests/test_tool_contract.py checks that every one is listed.
 * Keys are kebab-case Lucide names.
 */
export const iconTable: Record<string, Component> = {
  box: Box,
  code: Code,
  folder: Folder,
  keyboard: Keyboard,
  monitor: Monitor,
  zap: Zap,
}

export const fallbackIcon: Component = Box
