/// <reference types="vitest/config" />
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [vue()],
  server: { port: 5173, strictPort: true },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'] },
})
