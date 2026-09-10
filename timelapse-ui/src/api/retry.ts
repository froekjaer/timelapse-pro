/**
 * Limited automatic retries with backoff for transient failures only.
 *
 * Retried:   429, 502, 503, 504 and network failures (no HTTP status).
 * Never:     401/403 (access denied — retrying cannot help), other 4xx, 5xx.
 * Bounded:   maxRetries (default 2 → at most 3 attempts), capped delay,
 *            jitter to avoid retry storms in sync across tabs.
 */

export interface RetryOptions {
  maxRetries?: number
  baseDelayMs?: number
}

export function statusOf(err: unknown): number | undefined {
  if (typeof err === 'object' && err !== null) {
    const e = err as { status?: unknown; response?: { status?: unknown } }
    if (typeof e.status === 'number') return e.status
    if (typeof e.response?.status === 'number') return e.response.status
  }
  return undefined
}

export function isRetryableStatus(status: number | undefined): boolean {
  if (status === undefined) return true   // network failure, no response at all
  return status === 429 || status === 502 || status === 503 || status === 504
}

function retryAfterMs(err: unknown): number | undefined {
  const headers = (err as { response?: { headers?: Record<string, string> } })
    ?.response?.headers
  const raw = headers?.['retry-after'] ?? headers?.['Retry-After']
  const seconds = raw ? Number(raw) : NaN
  return Number.isFinite(seconds) ? seconds * 1000 : undefined
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  opts: RetryOptions = {},
): Promise<T> {
  const maxRetries = opts.maxRetries ?? 2
  const base = opts.baseDelayMs ?? 800
  let attempt = 0
  for (;;) {
    try {
      return await fn()
    } catch (err) {
      if (attempt >= maxRetries || !isRetryableStatus(statusOf(err))) throw err
      const backoff = base * 2 ** attempt + Math.random() * base * 0.5
      await delay(Math.min(retryAfterMs(err) ?? backoff, 10_000))
      attempt++
    }
  }
}
