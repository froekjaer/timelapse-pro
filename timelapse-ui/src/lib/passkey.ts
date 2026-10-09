// Passkey ceremonies must never be left hanging (2026-10-09).
// On macOS 27 / Safari 27 a WebAuthn request that is never finished can leave
// com.apple.AuthenticationServices.Helper stuck, after which every later
// Touch ID request in Safari waits until the Mac is rebooted — first seen
// 2026-09-24 from a passkey *registration* that hung (HANDOVER_LOG
// 2026-09-27). Login already had a deadline and a pagehide abort; these
// helpers give registration and the console step-up the same protection.
import { useEffect } from 'react'
import { WebAuthnAbortService } from '@simplewebauthn/browser'

export const PASSKEY_DEADLINE_MS = 75_000

/** Reject (and cancel the browser ceremony) if the passkey step stalls. */
export function withPasskeyDeadline<T>(ceremony: Promise<T>, ms = PASSKEY_DEADLINE_MS): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      WebAuthnAbortService.cancelCeremony()
      reject(new Error('Touch ID / Windows Hello svarede ikke. Prøv igen, eller brug adgangskode.'))
    }, ms)
  })
  return Promise.race([ceremony, deadline]).finally(() => clearTimeout(timer))
}

/** Cancel any pending passkey request when the page is left or unmounted. */
export function useAbortPasskeyOnLeave(): void {
  useEffect(() => {
    const abort = () => WebAuthnAbortService.cancelCeremony()
    window.addEventListener('pagehide', abort)
    return () => { window.removeEventListener('pagehide', abort); abort() }
  }, [])
}
