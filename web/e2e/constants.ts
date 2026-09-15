/** Single source of truth for the e2e setup - imported by both
 * playwright.config.ts (to launch the servers) and the specs (to log in). */

export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8199)
export const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 5199)

export const TEST_EMAIL = 'e2e@example.com'
export const TEST_PASSWORD = 'correct horse battery staple'
