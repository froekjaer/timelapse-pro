#!/usr/bin/env node
/**
 * ESLint "ratchet" gate — H-02 (GO_LIVE_CHECKLIST_v10.md §H).
 *
 * Formål: CI skal fejle hvis ANTAL eslint-problemer (fejl + advarsler) STIGER
 * i forhold til den kendte baseline. Vi kræver bevidst IKKE at alle
 * eksisterende problemer rettes før gaten kan aktiveres — kun at ingen nye
 * kommer til. Baseline sænkes manuelt i takt med at ældre problemer ryddes op
 * (se `Dokumentation/HANDOVER_LOG.md` for historik, senest 222 pr. 2026-07-04).
 *
 * Brug: `npm run lint:gate` (kører `eslint . -f json` internt).
 * Exit 0 = OK (uændret eller forbedret). Exit 1 = flere problemer end baseline.
 */
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const baselinePath = path.join(__dirname, '..', '.eslint-baseline.json')

const baseline = JSON.parse(readFileSync(baselinePath, 'utf-8'))

let output
try {
  output = execFileSync('npx', ['eslint', '.', '-f', 'json'], {
    cwd: path.join(__dirname, '..'),
    encoding: 'utf-8',
    maxBuffer: 1024 * 1024 * 50,
  })
} catch (err) {
  // eslint exits 1 når der er fejl — det er forventet, stdout indeholder stadig JSON.
  output = err.stdout ?? ''
  if (!output) {
    console.error('ESLint kunne ikke køres (ingen stdout):', err.message)
    process.exit(1)
  }
}

let results
try {
  results = JSON.parse(output)
} catch {
  console.error('Kunne ikke parse eslint JSON-output. Rå output:')
  console.error(output)
  process.exit(1)
}

const errorCount = results.reduce((sum, f) => sum + f.errorCount, 0)
const warningCount = results.reduce((sum, f) => sum + f.warningCount, 0)
const total = errorCount + warningCount

console.log(`ESLint: ${errorCount} fejl, ${warningCount} advarsler (${total} i alt)`)
console.log(`Baseline: ${baseline.total} (sat ${baseline.updated})`)

if (total > baseline.total) {
  console.error(
    `\n❌ ESLint-gate fejlede: ${total} problemer > baseline ${baseline.total}. ` +
      `Ret de nye problemer, eller opdater .eslint-baseline.json hvis stigningen er bevidst og godkendt.`
  )
  process.exit(1)
}

if (total < baseline.total) {
  console.log(
    `\n✅ Forbedring: ${baseline.total - total} færre problemer end baseline. ` +
      `Overvej at sænke baseline i .eslint-baseline.json til ${total}.`
  )
} else {
  console.log('\n✅ Uændret — ingen nye ESLint-problemer.')
}
