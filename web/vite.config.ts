/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    // e2e/ is Playwright's, run via `npm run test:e2e` - it has its own
    // `test`/`expect`, not vitest's, and the two must never collide here.
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
