// Browser login test (Peter 2026-10-11: login "SKAL bare virke ALTID").
// Starts its own Headend (uvicorn on a test Postgres) and the real login page
// (vite dev server proxying /api), then logs in through Chromium with a
// virtual authenticator standing in for Touch ID. Ports differ from the
// production Headend (8000) so it can also run on the Mac mini.
import { defineConfig } from '@playwright/test'
import path from 'node:path'

const WEB_PORT = 5199
const API_PORT = 8100
const ORIGIN = `http://localhost:${WEB_PORT}`
const python = process.env.E2E_PYTHON || 'python'
const databaseUrl = process.env.E2E_DATABASE_URL || 'postgresql://timelapse@localhost:5432/timelapse_e2e'
const headendDir = path.resolve(import.meta.dirname, '../../headend')

export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  retries: 0,
  reporter: [['list']],
  globalSetup: './global-setup.ts',
  use: { baseURL: ORIGIN, browserName: 'chromium', trace: 'retain-on-failure' },
  webServer: [
    {
      command: `${python} -m uvicorn main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: headendDir,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: databaseUrl,
        TIMELAPSE_ENV: 'test',
        JWT_SECRET: 'e2e-login-test-secret-0123456789abcdef',
        COOKIE_SECURE: 'false',
        BASE_URL: ORIGIN,
        ALLOWED_ORIGIN: ORIGIN,
        WEBAUTHN_ALLOWED_ORIGINS: ORIGIN,
        TIMELAPSE_ITIM_ENABLED: 'false',
        TIMELAPSE_EDGE_WAKE: '0',
        PYTHONPATH: [path.resolve(import.meta.dirname, '../..'), headendDir, path.resolve(import.meta.dirname, '../../edge')].join(path.delimiter),
      },
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      cwd: path.resolve(import.meta.dirname, '..'),
      url: `${ORIGIN}/login`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { TIMELAPSE_API_PROXY: `http://127.0.0.1:${API_PORT}`, VITE_API_URL: ORIGIN },
    },
  ],
})
