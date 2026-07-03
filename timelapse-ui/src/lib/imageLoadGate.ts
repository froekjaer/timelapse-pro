// Global gate: begræns SAMTIDIGE thumbnail-hentninger, så et stort galleri (fx 200)
// ikke slår data-fast/uvicorn ihjel med en byge på én gang. nginx står nu for
// rate-limit-undtagelsen (/api/thumbnails/ + /api/images/ uden limit_req) OG
// X-Accel-levering af selve filerne — derfor behøver gaten KUN et samtidigheds-
// loft (ingen rate-throttle mere), så billederne kommer hurtigt men kontrolleret.
// Justér MAX_CONCURRENT hvis data-fast presses; højere = hurtigere galleri.
const MAX_CONCURRENT = 12

let active = 0
const waiters: Array<() => void> = []

function drain() {
  while (active < MAX_CONCURRENT && waiters.length > 0) {
    active++
    waiters.shift()!()
  }
}

/**
 * Vent på en ledig slot. Returnerer en release-funktion der SKAL kaldes præcis én
 * gang (når billedet er hentet eller fejlede) for at frigive pladsen til næste.
 * release er idempotent — gentagne kald er harmløse.
 */
export function acquireImageSlot(): Promise<() => void> {
  let released = false
  const release = () => {
    if (released) return
    released = true
    active--
    drain()
  }
  return new Promise<() => void>((resolve) => {
    waiters.push(() => resolve(release))
    drain()
  })
}

// ── Delt IntersectionObserver ────────────────────────────────────────────────
// ÉT observer for ALLE kort i stedet for ét pr. kort. Afgørende ved gallerier med
// mange tusinde kort (fx Timelapse Video med 21.000 frames), hvor 21.000 separate
// observers ellers gør browseren ubrugelig. Kaldet fyrer én gang og af-observerer.
const _ioCallbacks = new Map<Element, () => void>()
let _io: IntersectionObserver | null = null

function _getIO(): IntersectionObserver {
  if (!_io) {
    _io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          const cb = _ioCallbacks.get(e.target)
          if (cb) { _ioCallbacks.delete(e.target); _io!.unobserve(e.target); cb() }
        }
      }
    }, { rootMargin: '400px' })
  }
  return _io
}

/** Kald cb én gang når el kommer i syne (±400px). Returnerer en cleanup-funktion. */
export function observeInView(el: Element, cb: () => void): () => void {
  _ioCallbacks.set(el, cb)
  _getIO().observe(el)
  return () => {
    if (_ioCallbacks.has(el)) { _ioCallbacks.delete(el); _io?.unobserve(el) }
  }
}
