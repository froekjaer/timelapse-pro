import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
const source = fs.readFileSync(new URL('../../src/api/retry.ts', import.meta.url), 'utf8')
function load() {
  const sandbox = { exports: {}, setTimeout, clearTimeout }
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, sandbox)
  return sandbox.exports
}
const err = status => { const e = new Error('x'); if (status !== undefined) e.status = status; return e }

test('retryable: 429/502/503/504/network; never 401/403/other client errors', () => {
  const r = load()
  for (const s of [429, 502, 503, 504, undefined]) assert.equal(r.isRetryableStatus(s), true, String(s))
  for (const s of [400, 401, 403, 404, 500]) assert.equal(r.isRetryableStatus(s), false, String(s))
  assert.equal(r.statusOf({ response: { status: 503 } }), 503)   // axios-shaped
  assert.equal(r.statusOf(err(503)), 503)                        // ApiError-shaped
  assert.equal(r.statusOf(new TypeError('fetch failed')), undefined)  // network failure
})

test('transient 503 is retried with bounded attempts and then succeeds', async () => {
  const r = load(); let calls = 0
  const out = await r.withRetry(() => { calls++; return calls < 3 ? Promise.reject(err(503)) : Promise.resolve('ok') }, { baseDelayMs: 1 })
  assert.equal(out, 'ok'); assert.equal(calls, 3)
})

test('access rejection (401/403) is never retried', async () => {
  const r = load()
  for (const s of [401, 403]) {
    let calls = 0
    await assert.rejects(r.withRetry(() => { calls++; return Promise.reject(err(s)) }, { baseDelayMs: 1 }))
    assert.equal(calls, 1, `status ${s}`)
  }
})

test('gives up after maxRetries — bounded, no retry storm', async () => {
  const r = load(); let calls = 0
  await assert.rejects(r.withRetry(() => { calls++; return Promise.reject(err(503)) }, { baseDelayMs: 1, maxRetries: 2 }))
  assert.equal(calls, 3)   // 1 initial + 2 retries, then the error propagates
})
