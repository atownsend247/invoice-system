import { defineConfig, devices } from '@playwright/test'
import { BACKEND_PORT, FRONTEND_PORT, TEST_EMAIL, TEST_PASSWORD } from './e2e/constants'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'bash e2e/start-backend.sh',
      url: `http://127.0.0.1:${BACKEND_PORT}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        E2E_BACKEND_PORT: String(BACKEND_PORT),
        E2E_EMAIL: TEST_EMAIL,
        E2E_PASSWORD: TEST_PASSWORD,
      },
    },
    {
      // --strictPort: fail fast instead of silently picking another port -
      // baseURL above needs to be right, not "whatever Vite landed on".
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        VITE_API_BASE_URL: `http://127.0.0.1:${BACKEND_PORT}`,
      },
    },
  ],
})
