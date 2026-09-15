// Standalone on purpose - no React, no api.ts (which touches import.meta.env,
// unavailable outside Vite's own module graph) - so Playwright's e2e fixtures
// can import this one constant without dragging in the whole app.
export const TOKEN_STORAGE_KEY = 'invoice-system.token'
