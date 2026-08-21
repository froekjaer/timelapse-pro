#!/usr/bin/env node
/**
 * sync-help-docs.mjs
 *
 * Kopierer de kuraterede brugerdokumenter fra repoets Dokumentation/-mappe
 * ind i UI'ens help-content-mappe, så /help-siden kan bundtle dem ved build.
 *
 * Single source of truth forbliver Markdown-filerne i Dokumentation/ —
 * kopierne herunder er genererede build-artefakter (gitignored).
 *
 * Køres automatisk via npm predev/prebuild. Kan køres manuelt:
 *   node scripts/sync-help-docs.mjs
 */
import { copyFileSync, mkdirSync, existsSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const uiRoot = resolve(here, '..')
const repoRoot = resolve(uiRoot, '..')
const outDir = join(uiRoot, 'src', 'help', 'content')

// slug -> fil i Dokumentation/ (relativt til repo-roden)
const DOCS = {
  'menuguide-bruger': 'Dokumentation/MENUGUIDE_BRUGER_v1.md',
  'menuguide-admin': 'Dokumentation/MENUGUIDE_ADMIN_v1.md',
  'faq': 'Dokumentation/FAQ_og_fejlsøgning.md',
  'brugermanual': 'Dokumentation/BRUGERMANUAL_v10.md',
  'adminmanual': 'Dokumentation/ADMINISTRATORMANUAL_v10.md',
}

mkdirSync(outDir, { recursive: true })

const missing = []
for (const [slug, rel] of Object.entries(DOCS)) {
  const src = join(repoRoot, rel)
  const dst = join(outDir, `${slug}.md`)
  if (existsSync(src)) {
    copyFileSync(src, dst)
    console.log(`help-docs: ${rel} -> src/help/content/${slug}.md`)
  } else {
    missing.push(rel)
    // Skriv en stub så importen ikke fejler, men gør manglen synlig i UI'et
    writeFileSync(dst, `# Dokument mangler\n\nKildefilen \`${rel}\` blev ikke fundet ved build. Kør \`node scripts/sync-help-docs.mjs\` fra \`timelapse-ui/\` i et fuldt repo-checkout.\n`)
    console.warn(`help-docs: ADVARSEL — ${rel} ikke fundet, stub skrevet`)
  }
}

if (missing.length > 0) {
  console.warn(`help-docs: ${missing.length} kildefil(er) manglede — se stubs i src/help/content/`)
}
