/** Opt-in, tab-local diagnostics. Never store raw URLs, headers or bodies. */
const ENABLED = 'tl_navigation_diagnostics_v1'
const REPORT = 'tl_navigation_report_v1'
const LIMIT = 300
export type Event = { at: string; ms: number; kind: string; name: string; values?: Record<string, number | string> }
let events: Event[] = []
let active = false
let started = false
let navigation = 0
let navigationStarted = 0
let waitOpen = false
let waitIsNavigation = false
let slowNavigations: Event[][] = []
let persistTimer: ReturnType<typeof setTimeout> | undefined
const observers: PerformanceObserver[] = []
const routes = new Set(['backup', 'global-config', 'tags', 'settings', 'ai', 'compliance', 'help', 'system-admin', 'local-access', 'users', 'key-management', 'ssh-tunnel', 'updates', 'change-tickets', 'post-processing', 'cmdb', 'import', 'siem', 'edge-communications', 'retention', 'redaction', 'observability', 'openwebui'])
export function safeName(raw: string): string {
  try {
    const url = new URL(raw, window.location.origin)
    if (url.origin !== window.location.origin) return 'external'
    const p = url.pathname.split('/').filter(Boolean)
    if (p[0] === 'assets') return 'script-or-style'
    if (p[0] === 'api') {
      if (p[1] === 'admin' && ['devices', 'captures', 'stats', 'customers', 'sites', 'settings'].includes(p[2])) return `/api/admin/${p[2]}`
      if (['thumbnails', 'images', 'updates', 'auth'].includes(p[1])) return `/api/${p[1]}`
      return '/api/other'
    }
    if (!p.length) return '/'
    if (['devices', 'cameras', 'customers', 'sites'].includes(p[0])) return `/${p[0]}/:id`
    return routes.has(p[0]) ? `/${p[0]}` : '/other'
  } catch { return 'unknown' }
}
function persist() {
  if (persistTimer !== undefined) return
  persistTimer = setTimeout(() => {
    persistTimer = undefined
    if (!active) return
    try { sessionStorage.setItem(REPORT, JSON.stringify({ events, slowNavigations })) } catch { /* Diagnostics must not break navigation. */ }
  }, 250)
}
export function record(kind: string, name: string, values?: Event['values']) {
  if (!active) return
  events.push({ at: new Date().toISOString(), ms: Math.round(performance.now()), kind, name, values })
  events = events.slice(-LIMIT)
  persist()
}
export function diagnosticsEnabled() { return active }
export function enableDiagnostics() {
  try { sessionStorage.setItem(ENABLED, '1'); sessionStorage.removeItem(REPORT) } catch { return false }
  window.location.reload()
  return true
}
export function stopDiagnostics() {
  active = false
  observers.forEach(o => o.disconnect())
  try { sessionStorage.removeItem(ENABLED); sessionStorage.removeItem(REPORT) } catch { /* private mode */ }
  events = []
  slowNavigations = []
  if (persistTimer !== undefined) clearTimeout(persistTimer)
  persistTimer = undefined
}
export function report() {
  return JSON.stringify({ version: 1, scope: 'this-tab-only', note: 'Times are observations, not proof of causation. frame-ready is a rendering opportunity, not pixel paint. SQL excludes pool wait/fetch; missing server timings mean unavailable.', events, slowNavigations }, null, 2)
}
export function phase(name: string) {
  // A data-wait outside an open navigation (e.g. the 60 s auto-refresh) starts
  // its own clock — otherwise a refresh would be measured as a 60-120 s
  // "navigation" from the last real navigation.
  if (name.endsWith('-data-wait') && !waitOpen) {
    navigationStarted = performance.now()
    waitIsNavigation = false
    waitOpen = true
  }
  record('phase', name, { navigation })
}
export function beginNavigation(path: string, startMs?: number) {
  navigation++
  navigationStarted = startMs ?? performance.now()
  waitOpen = true
  waitIsNavigation = true
  record('navigation', safeName(path), { navigation, hidden: document.hidden ? 1 : 0 })
}
export function loadFailed(name: string) {
  // A loading state that ended with an error is NOT a successful page load:
  // record the failure, never a frame-ready, and never a slow-navigation snapshot.
  if (!active) return
  record('load-failed', name, { navigation })
  waitOpen = false
}
export function frameReady(name: string) {
  if (!active) return
  const id = navigation
  const first = requestAnimationFrame(() => {
    second = requestAnimationFrame(() => {
      if (navigation !== id || !active) return
      const elapsed = performance.now() - navigationStarted
      record('frame-ready', name, { navigation, elapsed, refresh: waitIsNavigation ? 0 : 1, hidden: document.hidden ? 1 : 0 })
      if (waitIsNavigation && elapsed >= 3000 && !document.hidden) {
        slowNavigations.push(events.filter(e => e.ms >= navigationStarted))
        slowNavigations = slowNavigations.slice(-3)
        persist()
      }
      waitOpen = false
    })
  })
  let second = 0
  return () => { cancelAnimationFrame(first); cancelAnimationFrame(second) }
}
export function startDiagnostics() {
  if (started) return
  started = true
  try { active = sessionStorage.getItem(ENABLED) === '1' } catch { return }
  if (!active) return
  // Previously saved events are generated by this module. Do not trust imported storage data.
  // Only retain current-document events; Resource Timing includes startup entries via buffered observers.
  events = []
  // First load is measured from the document navigation start (time origin 0),
  // not from when this module happened to run.
  beginNavigation(window.location.pathname, 0)
  phase('bootstrap-start')
  const originalFetch = window.fetch.bind(window)
  window.fetch = (input, init) => {
    try {
      const u = new URL(input instanceof Request ? input.url : String(input), location.href)
      if (active && u.origin === location.origin && u.pathname.startsWith('/api/')) {
        const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
        headers.set('X-TLP-Diagnostics', '1')
        record('request-dispatch', safeName(u.href), { navigation })
        return originalFetch(input, { ...init, headers }).then(response => {
          record('response-headers', safeName(u.href), { status: response.status })
          return response
        }, error => { record('request-error', safeName(u.href)); throw error })
      }
    } catch { /* Leave unusual request inputs to native fetch. */ }
    return originalFetch(input, init)
  }
  document.addEventListener('click', e => {
    if (!(e instanceof MouseEvent) || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    const a = (e.target as Element | null)?.closest?.('a')
    if (!a || a.target === '_blank' || a.hasAttribute('download')) return
    try { const u = new URL(a.href); if (u.origin === location.origin) beginNavigation(u.pathname) } catch { /* ignore */ }
  }, true)
  window.addEventListener('popstate', () => beginNavigation(location.pathname))
  document.addEventListener('visibilitychange', () => record('visibility', document.hidden ? 'hidden' : 'visible'))
  window.addEventListener('error', () => phase('browser-error'))
  window.addEventListener('unhandledrejection', () => phase('unhandled-rejection'))
  if (typeof PerformanceObserver === 'undefined') { phase('resource-observer-unavailable'); return }
  for (const type of ['resource', 'navigation', 'longtask']) {
    if (!PerformanceObserver.supportedEntryTypes?.includes(type)) continue
    const observer = new PerformanceObserver(list => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'longtask') { record('longtask', 'main-thread', { start: entry.startTime, duration: entry.duration }); continue }
        const r = entry as PerformanceResourceTiming
        const values: Record<string, number | string> = {
          start: r.startTime, duration: r.duration, fetchStart: r.fetchStart,
          dns: r.domainLookupEnd - r.domainLookupStart,
          connect: r.connectEnd - r.connectStart,
          requestStart: r.requestStart, responseStart: r.responseStart, responseEnd: r.responseEnd,
          transferBytes: r.transferSize, encodedBytes: r.encodedBodySize,
        }
        for (const t of r.serverTiming || []) {
          if (['app', 'sql', 'sql_count', 'loop_lag'].includes(t.name)) values[t.name] = t.duration
          if (t.name === 'trace' && /^[a-f0-9]{32}$/.test(t.description)) values.trace = t.description
        }
        record(entry.entryType, safeName(r.name), values)
      }
    })
    observer.observe({ type, buffered: true })
    observers.push(observer)
  }
}
