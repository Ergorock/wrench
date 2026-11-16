import type { Component } from 'vue'
import {
  AppWindow,
  Box,
  BookOpen,
  Boxes,
  Calculator,
  Code,
  Folder,
  FolderKanban,
  GitBranch,
  GitFork,
  Keyboard,
  Monitor,
  QrCode,
  ServerCog,
  Terminal,
  Trash2,
  Wrench,
  Zap,
} from '@lucide/vue'

/**
 * Icons that can be looked up by name (category icons from `core/categories.py`, `MANIFEST.icon`
 * of tools). Explicit named imports keep the bundle tree-shaken. To use a new icon in a manifest
 * or category, add it here: backend/tests/test_tool_contract.py checks that every one is listed.
 * Keys are kebab-case Lucide names.
 */
export const iconTable: Record<string, Component> = {
  'app-window': AppWindow,
  box: Box,
  'book-open': BookOpen,
  boxes: Boxes,
  calculator: Calculator,
  code: Code,
  folder: Folder,
  'folder-kanban': FolderKanban,
  'git-branch': GitBranch,
  'git-fork': GitFork,
  keyboard: Keyboard,
  monitor: Monitor,
  'qr-code': QrCode,
  'server-cog': ServerCog,
  terminal: Terminal,
  'trash-2': Trash2,
  wrench: Wrench,
  zap: Zap,
}

export const fallbackIcon: Component = Box
