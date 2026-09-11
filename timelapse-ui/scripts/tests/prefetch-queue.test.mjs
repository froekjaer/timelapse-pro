import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
const source = fs.readFileSync(new URL('../../src/lib/prefetchQueue.ts', import.meta.url), 'utf8')
function load() {
  const sandbox = { exports: {}, setTimeout, clearTimeout }
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, sandbox)
  return sandbox.exports
}

// Test-harness: synkron "loader" der registrerer rækkefølgen, og en scheduler
// der kører straks (svarer til at browseren altid er idle).
function harness() {
  const q = load().createPrefetchQueue
  const loaded = []
  const queue = q((url, done) => { loaded.push(url); done() }, cb => cb())
  return { queue, loaded }
}

test('loads targets sequentially in nearest-first order, dedupes', () => {
  const { queue, loaded } = harness()
  queue.setTargets(['a', 'b', 'b', 'c'])
  assert.deepEqual(loaded, ['a', 'b', 'c'])
  assert.equal(queue.pending(), 0)
  assert.equal(queue.isDone('b'), true)
})

test('reordering moves new neighbours to front, never refetches completed', () => {
  const { queue, loaded } = harness()
  queue.setTargets(['a', 'b', 'c'])
  assert.deepEqual(loaded, ['a', 'b', 'c'])
  // Brugeren bladrer tilbage: 'x' og 'b' er nye naboer — 'b' er allerede hentet
  queue.setTargets(['x', 'b', 'y'])
  assert.deepEqual(loaded, ['a', 'b', 'c', 'x', 'y'])
})

test('cancel stops the queue; in-flight finishes; new targets start fresh', () => {
  const q = load().createPrefetchQueue
  const started = []
  const dones = new Map()
  const queue = q((url, done) => { started.push(url); dones.set(url, done) }, cb => cb())
  queue.setTargets(['a', 'b', 'c'])
  assert.deepEqual(started, ['a'])          // én ad gangen: kun 'a' er undervejs
  queue.cancel()
  assert.equal(queue.pending(), 0)
  dones.get('a')()                          // 'a' fuldfører EFTER cancel
  assert.deepEqual(started, ['a'])          // intet nyt starter — køen var tom
  assert.equal(queue.isDone('a'), true)     // men den blev faktisk hentet
  queue.setTargets(['z'])
  assert.deepEqual(started, ['a', 'z'])     // ny generation starter korrekt
})

test('in-flight completion after cancel keeps the new queue moving', () => {
  const q = load().createPrefetchQueue
  const dones = new Map()
  const queue = q((url, done) => { dones.set(url, done) }, cb => cb())
  queue.setTargets(['a', 'b'])
  queue.cancel()
  queue.setTargets(['c'])                   // pump blokeres af 'a' in-flight
  dones.get('a')()                          // 'a' fuldfører → ny generation skal videre
  assert.ok(dones.has('c'), 'c blev hentet efter at a fuldførte')
  dones.get('c')()
  assert.equal(queue.pending(), 0)
  assert.equal(queue.isDone('a'), true)
})
