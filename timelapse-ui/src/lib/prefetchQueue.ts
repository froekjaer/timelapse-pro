// Sekventiel baggrunds-prefetch af fuldopløste billeder (2026-09-11, Kimi).
//
// Baggrund: Lightbox-browsing hentede 5–6 MB fuldbilleder ét ad gangen SYNKRONT
// ved hvert piletast-skift. På trænge netværksveje (hairpin via offentlig IP /
// begrænset upload) mætter det linket, så selv små API-kald kommer i kø bag
// billeddata (målt: 3,7 s delay på /users mens serveren brugte 12 ms).
//
// Løsning: Lightbox viser thumbnail øjeblikkeligt og opgraderer til fuld
// opløsning i baggrunden. Denne kø henter naboer først og derefter resten af
// galleriet — nærmest-først, ÉN ad gangen, kun via scheduleren (idle i browseren),
// så prefetch aldrig konkurrerer med brugerens egne klik.
//
// Kernen (createPrefetchQueue) er en ren fabrik uden DOM, så den kan testes med
// node --test. Browser-bindingen bor i bunden af filen.

export type PrefetchLoader = (url: string, done: () => void) => void
export type PrefetchScheduler = (cb: () => void) => void

export interface PrefetchQueue {
  /** Erstat køen. Allerede hentede URL'er huskes og springes over. */
  setTargets: (urls: string[]) => void
  /** Tøm køen (fx når Lightbox lukker). Huskede URL'er bevares. */
  cancel: () => void
  /** Antal URL'er der venter i køen (til tests/diagnostik). */
  pending: () => number
  /** Om en URL allerede er hentet færdig af køen. */
  isDone: (url: string) => boolean
}

export function createPrefetchQueue(load: PrefetchLoader, schedule: PrefetchScheduler): PrefetchQueue {
  let targets: string[] = []
  const completed = new Set<string>()
  let inFlight = false
  let generation = 0 // stiger ved setTargets/cancel → forældede callbacks ignoreres

  function pump(gen: number) {
    if (inFlight || gen !== generation) return
    // Find næste URL der ikke allerede er hentet
    while (targets.length > 0 && completed.has(targets[0])) targets.shift()
    const url = targets.shift()
    if (!url) return
    inFlight = true
    load(url, () => {
      inFlight = false
      completed.add(url) // den ER hentet — køen må aldrig hente den igen
      // Hvis køen blev udskiftet/annulleret imens, skal vi alligevel sikre at
      // den AKTUELLE generation kommer videre — ellers kunne køen gå i stå.
      schedule(() => pump(generation))
    })
  }

  return {
    setTargets(urls: string[]) {
      generation++
      const gen = generation
      // Dedupe, bevar rækkefølge, spring allerede hentede over
      const seen = new Set<string>()
      targets = urls.filter(u => {
        if (completed.has(u) || seen.has(u)) return false
        seen.add(u)
        return true
      })
      schedule(() => pump(gen))
    },
    cancel() {
      generation++
      targets = []
    },
    pending: () => targets.filter(u => !completed.has(u)).length,
    isDone: (url: string) => completed.has(url),
  }
}

// ── Browser-singleton ─────────────────────────────────────────────────────────
// Én global kø: der er kun én Lightbox ad gangen, og galleri + Lightbox deler
// både kø og browserens HTTP-cache.

function browserLoad(url: string, done: () => void) {
  const img = new Image()
  img.onload = () => done()
  img.onerror = () => done() // fejl må ikke standse køen — næste billede prøves
  img.src = url
}

function idleSchedule(cb: () => void) {
  // Udsæt mens fanen er skjult: ingen grund til at bruge båndbredde for en
  // baggrunds-tab. Genforsøg roligt (5 s) — aldrig tæt loop.
  if (typeof document !== 'undefined' && document.hidden) {
    setTimeout(() => idleSchedule(cb), 5000)
    return
  }
  const ric = (window as unknown as { requestIdleCallback?: (fn: () => void, opts?: { timeout: number }) => void })
    .requestIdleCallback
  if (ric) ric(cb, { timeout: 2000 })
  else setTimeout(cb, 250)
}

const browserQueue = createPrefetchQueue(browserLoad, idleSchedule)

/** Prefetch fuldopløste billeder i baggrunden, nærmest-først (rækkefølgen i urls). */
export function setPrefetchTargets(urls: string[]) {
  browserQueue.setTargets(urls)
}

/** Stop baggrundsprefetch (fx når Lightbox lukker). */
export function cancelPrefetch() {
  browserQueue.cancel()
}

/** Om prefetch-køen allerede har hentet en URL færdig (til tests/diagnostik). */
export function isPrefetched(url: string) {
  return browserQueue.isDone(url)
}
