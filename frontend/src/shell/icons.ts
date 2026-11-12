import type { Component } from 'vue'
import { Box, icons } from 'lucide-vue-next'

const lookup = icons as Record<string, Component>

/** Lucide component for a kebab-case icon name (`monitor`, `file-text`…); `Box` if unknown. */
export function lucideIcon(name: string): Component {
  const pascal = name.replace(/(^|-)([a-z0-9])/g, (_, __, c: string) => c.toUpperCase())
  return lookup[pascal] ?? Box
}
