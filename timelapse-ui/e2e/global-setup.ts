import { execFileSync } from 'node:child_process'
import path from 'node:path'

export const LOGIN_USER_FILE = path.resolve(import.meta.dirname, '.login-user.json')

export default function globalSetup() {
  const headendDir = path.resolve(import.meta.dirname, '../../headend')
  execFileSync(process.env.E2E_PYTHON || 'python', [path.resolve(import.meta.dirname, 'seed_login_user.py'), LOGIN_USER_FILE], {
    cwd: headendDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      DATABASE_URL: process.env.E2E_DATABASE_URL || 'postgresql://timelapse@localhost:5432/timelapse_e2e',
      TIMELAPSE_ENV: 'test',
      PYTHONPATH: [path.resolve(import.meta.dirname, '../..'), headendDir, path.resolve(import.meta.dirname, '../../edge')].join(path.delimiter),
    },
  })
}
