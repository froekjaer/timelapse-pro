// Login through the real page, Headend and database (Peter 2026-10-11).
// Chromium's virtual authenticator holds the seeded passkey and plays Touch ID.
import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import { LOGIN_USER_FILE } from './global-setup'

interface LoginUser {
  username: string; password: string; rpId: string
  credentialId: string; userHandle: string; privateKey: string
}
const user = (): LoginUser => JSON.parse(fs.readFileSync(LOGIN_USER_FILE, 'utf8'))

let signCounter = 0
const nextSignCount = () => (signCounter += 1000)

async function addTouchId(page: Page, { responds = true, verified = true } = {}) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('WebAuthn.enable')
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: {
      protocol: 'ctap2', transport: 'internal', hasResidentKey: true,
      hasUserVerification: true, isUserVerified: verified,
      // false = the "Touch ID never answers" case
      automaticPresenceSimulation: responds,
    },
  })
  const u = user()
  await cdp.send('WebAuthn.addCredential', {
    authenticatorId,
    credential: {
      credentialId: u.credentialId, isResidentCredential: true, rpId: u.rpId,
      // Each test gets a fresh virtual authenticator for the same seeded key;
      // a strictly rising counter keeps the server's clone detection satisfied
      // (deterministic: not tied to the wall clock — Codex review on #301).
      privateKey: u.privateKey, userHandle: u.userHandle, signCount: nextSignCount(),
    },
  })
  return { cdp, authenticatorId }
}

// Register the wait before navigating: the mount-time prefetch can finish
// before a waiter added after goto() exists (Codex review on #301).
async function gotoLoginWithPrefetch(page: Page) {
  await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/auth/webauthn/login-begin')),
    page.goto('/login'),
  ])
}

async function expectLoggedIn(page: Page) {
  await page.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 20_000 })
  const me = await page.request.get('/api/auth/me')
  expect(me.status()).toBe(200)
  expect((await me.json()).username).toBe(user().username)
}

test('the login page prepares Touch ID ahead and never starts an AutoFill request', async ({ page }) => {
  const begins: string[] = []
  page.on('request', r => { if (r.url().endsWith('/api/auth/webauthn/login-begin')) begins.push(r.postData() ?? '') })
  await page.goto('/login')
  await expect(page.getByText('Log ind med Windows Hello / Touch ID')).toBeVisible()
  await page.waitForTimeout(1500)
  expect(begins).toEqual(['{}'])          // one prefetched challenge, nothing pending in the browser
})

test('Touch ID button logs in without typing anything', async ({ page }) => {
  await addTouchId(page)
  await gotoLoginWithPrefetch(page)
  await page.getByText('Log ind med Windows Hello / Touch ID').click()
  await expectLoggedIn(page)
})

test('Touch ID button asks the authenticator inside the click (no request first)', async ({ page }) => {
  // Safari only honours a passkey request made directly in the click.
  await addTouchId(page)
  await gotoLoginWithPrefetch(page)
  const beforeClick: string[] = []
  page.on('request', r => beforeClick.push(r.url()))
  await page.getByText('Log ind med Windows Hello / Touch ID').click()
  await expectLoggedIn(page)
  const firstApiCall = beforeClick.find(u => u.includes('/api/'))
  expect(firstApiCall).toContain('/api/auth/webauthn/login-complete')
})

test('Touch ID works on the next click after a failed attempt', async ({ page }) => {
  // First attempt: fingerprint not recognised (user verification fails).
  const { cdp, authenticatorId } = await addTouchId(page, { verified: false })
  await gotoLoginWithPrefetch(page)
  const refreshed = page.waitForResponse(r => r.url().endsWith('/api/auth/webauthn/login-begin'))
  await page.getByText('Log ind med Windows Hello / Touch ID').click()
  await expect(page.locator('text=/Touch ID|Windows Hello|godkendt/').first()).toBeVisible()
  await refreshed                                   // a fresh challenge is ready again
  await cdp.send('WebAuthn.setUserVerified', { authenticatorId, isUserVerified: true })
  await page.getByText('Log ind med Windows Hello / Touch ID').click()
  await expectLoggedIn(page)
})

test('password login', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('admin').fill(user().username)
  await page.locator('input[type="password"]').fill(user().password)
  await page.getByRole('button', { name: 'Log ind', exact: true }).click()
  await expectLoggedIn(page)
})

test('Touch ID that never answers hits the page deadline: error and server report, never an endless spinner', async ({ page }) => {
  // The login page's own 75 s deadline (LoginPage.tsx) is what ended the
  // 2026-10-13 Safari case (an extension swallowing the request). Chromium
  // would otherwise stop at the server's 60 s WebAuthn timeout first, so the
  // options are given a long timeout here: only the page deadline can end it.
  test.setTimeout(150_000)
  await page.route('**/api/auth/webauthn/login-begin', async route => {
    const response = await route.fetch()
    const options = await response.json()
    await route.fulfill({ response, json: { ...options, timeout: 600_000 } })
  })
  await addTouchId(page, { responds: false })
  await gotoLoginWithPrefetch(page)
  const report = page.waitForRequest(r => r.url().endsWith('/api/auth/webauthn/client-report'), { timeout: 100_000 })
  await page.getByText('Log ind med Windows Hello / Touch ID').click()
  const body = JSON.parse((await report).postData() ?? '{}')
  expect(body.stage).toBe('touch-id')
  expect(body.message).toContain('svarede ikke')
  await expect(page.getByText('svarede ikke')).toBeVisible()
  await expect(page.getByText('Log ind med Windows Hello / Touch ID')).toBeEnabled()
})
