import type { Component } from 'vue'
import { fallbackIcon, iconTable } from './iconTable'

/** Lucide component for a kebab-case icon name from `iconTable` (`monitor`, `keyboard`…); `Box` if unknown. */
export function lucideIcon(name: string): Component {
  return Object.hasOwn(iconTable, name) ? iconTable[name] : fallbackIcon
}
