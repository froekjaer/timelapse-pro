import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
const source = fs.readFileSync(new URL('../../src/diagnostics/timingRecorder.ts', import.meta.url), 'utf8')
function setup(enabled = true) {
  const data = new Map(enabled ? [['tl_navigation_diagnostics_v1', '1']] : [])
  const calls = []; const observers = []; const handlers = {}; const frames = []; const clock = {now:10}
  const location = {origin:'https://example.test', pathname:'/devices/PRIVATE-ID', href:'https://example.test/devices/PRIVATE-ID', reload() {}}
  const sandbox = { exports: {}, URL, Headers, Request, Date, JSON, setTimeout, clearTimeout, performance:{now:()=>clock.now}, location,
    sessionStorage: {getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)},
    document:{hidden:false,addEventListener:(k,f)=>handlers[k]=f}, requestAnimationFrame:cb=>{frames.push(cb);return frames.length},cancelAnimationFrame(){},
    PerformanceObserver: class {static supportedEntryTypes=['resource','navigation','longtask']; constructor(cb){this.cb=cb;observers.push(this)} observe(){} disconnect(){}},
  }
  sandbox.window={location,fetch:(...args)=>{calls.push(args);return Promise.resolve('ok')},addEventListener(){}}
  vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,sandbox)
  return { api:sandbox.exports,data,calls,observers,sandbox,frames,clock }
}
test('disabled default collects nothing and leaves fetch untouched',()=>{
 const {api,sandbox}=setup(false);const original=sandbox.window.fetch;api.startDiagnostics();api.phase('test');assert.equal(sandbox.window.fetch,original);assert.equal(JSON.parse(api.report()).events.length,0)
})
test('sanitizes all dynamic paths, secrets, external URLs and timing descriptions',()=>{
 const {api,observers}=setup();api.startDiagnostics()
 assert.equal(api.safeName('/devices/PRIVATE-ID?token=SECRET'),'/devices/:id')
 assert.equal(api.safeName('/api/admin/captures?filename=PRIVATE'),'/api/admin/captures')
 assert.equal(api.safeName('https://other.test/private'), 'external')
 observers[0].cb({getEntries:()=>[{entryType:'resource',name:'https://example.test/api/images/PRIVATE?token=SECRET',startTime:1,duration:2,serverTiming:[{name:'trace',description:'SECRET'},{name:'app',duration:2}]}]})
 assert.doesNotMatch(api.report(),/PRIVATE|SECRET|other.test/)
})
test('bounded report; stop clears state and stops adding headers',async()=>{
 const {api,sandbox,data,calls}=setup();api.startDiagnostics();for(let i=0;i<400;i++)api.phase('test')
 assert.equal(JSON.parse(api.report()).events.length,300)
 await sandbox.window.fetch('/api/test',{headers:{'X-Keep':'value'},credentials:'include'})
 assert.equal(calls[0][1].headers.get('X-TLP-Diagnostics'),'1');assert.equal(calls[0][1].headers.get('X-Keep'),'value');assert.equal(calls[0][1].credentials,'include')
 await sandbox.window.fetch('https://other.test/api/test');assert.equal(calls[1][1],undefined)
 api.stopDiagnostics();api.phase('ignored');assert.equal(JSON.parse(api.report()).events.length,0);assert.equal(data.size,0)
 await sandbox.window.fetch('/api/test');assert.equal(calls[2][1],undefined)
})

test('retains a slow navigation separately, excludes stale and hidden frames',()=>{
 const {api,frames,clock,sandbox}=setup();api.startDiagnostics();api.frameReady('dashboard')
 clock.now=4010;frames.shift()();frames.shift()()
 assert.equal(JSON.parse(api.report()).slowNavigations.length,1)
 api.beginNavigation('/devices/private');api.frameReady('device');api.beginNavigation('/tags')
 frames.shift()();frames.shift()();assert.equal(JSON.parse(api.report()).slowNavigations.length,1)
 api.frameReady('tags');clock.now=9010;sandbox.document.hidden=true;frames.shift()();frames.shift()()
 assert.equal(JSON.parse(api.report()).slowNavigations.length,1);api.stopDiagnostics()
})
