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

async function addTouchId(page: Page, { responds = true } = {}) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('WebAuthn.enable')
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: {
      protocol: 'ctap2', transport: 'internal', hasResidentKey: true,
      hasUserVerification: true, isUserVerified: true,
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
}

// Take AutoFill out of the picture so the button path is what logs in — also
// the situation when AutoFill itself is broken (2026-10-10/11) or missing.
async function withoutAutofill(page: Page) {
  await page.route('**/api/auth/webauthn/login-begin', route =>
    route.request().postData() === '{}'
      ? route.fulfill({ status: 503, body: '{"detail":"AutoFill disabled by test"}' })
      : route.continue())
}

async function expectLoggedIn(page: Page) {
  await page.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 20_000 })
  const me = await page.request.get('/api/auth/me')
  expect(me.status()).toBe(200)
  expect((await me.json()).username).toBe(user().username)
}

test('the login page loads and the passkey AutoFill start answers 200', async ({ page }) => {
  // The 2026-10-10/11 production fault: this request returned 500 on every page load.
  const autofillBegin = page.waitForResponse(r =>
    r.url().endsWith('/api/auth/webauthn/login-begin') && r.request().postData() === '{}')
  await page.goto('/login')
  expect((await autofillBegin).status()).toBe(200)
  await expect(page.getByText('Log ind med Windows Hello / Touch ID')).toBeVisible()
})

test('passkey AutoFill logs in straight from the login page', async ({ page }) => {
  // Chromium's virtual authenticator answers the conditional (AutoFill)
  // request itself, as choosing the suggested passkey does in Safari.
  await addTouchId(page)
  await page.goto('/login')
  await expectLoggedIn(page)
})

test('passkey login with the Touch ID button', async ({ page }) => {
  await addTouchId(page)
  await withoutAutofill(page)
  await page.goto('/login')
  await page.getByPlaceholder('admin').fill(user().username)
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

test('Touch ID that never answers offers the password path within 10 s', async ({ page }) => {
  await addTouchId(page, { responds: false })
  await withoutAutofill(page)
  await page.goto('/login')
  await page.getByPlaceholder('admin').fill(user().username)
  await page.getByText('Log ind med Windows Hello / Touch ID').click()
  const fallback = page.getByRole('button', { name: 'Brug adgangskode i stedet' })
  await expect(fallback).toBeVisible({ timeout: 12_000 })
  await fallback.click()
  await expect(fallback).toBeHidden()
  await expect(page.locator('input[type="password"]')).toBeFocused()
  await page.locator('input[type="password"]').fill(user().password)
  await page.getByRole('button', { name: 'Log ind', exact: true }).click()
  await expectLoggedIn(page)
})
