/**
 * Overskrifts-udtræk til /help-siden (sidebar-indholdsfortegnelse og søgning).
 * Skilt fra markdown.tsx for at overholde react-refresh/only-export-components.
 */

export interface Heading {
  level: number
  text: string
  id: string
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[æ]/g, 'ae')
    .replace(/[ø]/g, 'oe')
    .replace(/[å]/g, 'aa')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/** Udtræk overskrifter (til sidebar/søgning) fra rå markdown. */
export function extractHeadings(md: string): Heading[] {
  const headings: Heading[] = []
  let inFence = false
  for (const line of md.split('\n')) {
    if (line.trimStart().startsWith('```')) {
      inFence = !inFence
      continue
    }
    if (inFence) continue
    const m = /^(#{1,4})\s+(.+)$/.exec(line)
    if (m) {
      const text = m[2].replace(/\*\*/g, '').replace(/`/g, '').trim()
      headings.push({ level: m[1].length, text, id: slugify(text) })
    }
  }
  return headings
}
