import type { Component } from 'vue'

const modules = import.meta.glob<{ default: () => Promise<Component> }>('../tools/*/index.ts', {
  eager: true,
})

export const toolLoaders: Record<string, () => Promise<Component>> = {}
for (const [path, mod] of Object.entries(modules)) {
  const m = /\.\.\/tools\/([^/]+)\/index\.ts$/.exec(path)
  if (m) toolLoaders[m[1]] = mod.default
}
