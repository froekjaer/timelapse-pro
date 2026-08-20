import { useMemo, useState } from 'react'
import { BookOpen, LifeBuoy, Search, ShieldCheck, UserRound, Wrench } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Markdown } from '../help/markdown'
import { extractHeadings, slugify } from '../help/headings'

import menuguideBruger from '../help/content/menuguide-bruger.md?raw'
import menuguideAdmin from '../help/content/menuguide-admin.md?raw'
import faq from '../help/content/faq.md?raw'
import brugermanual from '../help/content/brugermanual.md?raw'
import adminmanual from '../help/content/adminmanual.md?raw'

/**
 * /help — in-app dokumentation.
 *
 * Indholdet bundtles ved build fra repoets Markdown-dokumenter via
 * scripts/sync-help-docs.mjs (npm predev/prebuild), så hjælpen altid matcher
 * den deployede version og virker uden internet (også på edge-enheders
 * lokale management-UI).
 */

interface HelpDoc {
  slug: string
  title: string
  description: string
  icon: typeof BookOpen
  source: string
  adminOnly: boolean
}

const DOCS: HelpDoc[] = [
  {
    slug: 'faq',
    title: 'FAQ & fejlsøgning',
    description: 'De hyppigste problemer og deres løsning — spørgsmål/svar.',
    icon: LifeBuoy,
    source: faq,
    adminOnly: false,
  },
  {
    slug: 'menuguide-bruger',
    title: 'Menuguide — Bruger',
    description: 'Hver side i menuen forklaret felt for felt.',
    icon: UserRound,
    source: menuguideBruger,
    adminOnly: false,
  },
  {
    slug: 'brugermanual',
    title: 'Brugermanual',
    description: 'Opgaveorienteret manual: login, billeder, tags, video, rapporter.',
    icon: BookOpen,
    source: brugermanual,
    adminOnly: false,
  },
  {
    slug: 'menuguide-admin',
    title: 'Menuguide — Admin',
    description: 'Alle Admin-dropdownens undermenuer forklaret felt for felt.',
    icon: ShieldCheck,
    source: menuguideAdmin,
    adminOnly: true,
  },
  {
    slug: 'adminmanual',
    title: 'Administratormanual',
    description: 'Drift, backup, provisioning, update-flow, sikkerhedsprocedurer.',
    icon: Wrench,
    source: adminmanual,
    adminOnly: true,
  },
]

interface SearchHit {
  doc: HelpDoc
  heading: string
  headingId: string
  snippet: string
}

function searchDocs(docs: HelpDoc[], query: string): SearchHit[] {
  const q = query.trim().toLowerCase()
  if (q.length < 2) return []
  const hits: SearchHit[] = []
  for (const doc of docs) {
    const lines = doc.source.split('\n')
    let currentHeading = doc.title
    let currentId = ''
    for (const line of lines) {
      const h = /^(#{1,4})\s+(.+)$/.exec(line)
      if (h) {
        currentHeading = h[2].replace(/\*\*/g, '').replace(/`/g, '').trim()
        currentId = slugify(currentHeading)
      }
      const idx = line.toLowerCase().indexOf(q)
      if (idx !== -1) {
        const start = Math.max(0, idx - 40)
        const snippet = line.slice(start, idx + q.length + 60).trim()
        hits.push({ doc, heading: currentHeading, headingId: currentId, snippet })
        if (hits.length >= 25) return hits
      }
    }
  }
  return hits
}

export function HelpPage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('super_admin', 'admin')
  const visibleDocs = useMemo(() => DOCS.filter((d) => !d.adminOnly || isAdmin), [isAdmin])

  const [selectedSlug, setSelectedSlug] = useState('faq')
  const [query, setQuery] = useState('')

  const selected = visibleDocs.find((d) => d.slug === selectedSlug) ?? visibleDocs[0]
  const headings = useMemo(() => extractHeadings(selected.source), [selected])
  const hits = useMemo(() => searchDocs(visibleDocs, query), [visibleDocs, query])

  function goto(docSlug: string, headingId?: string) {
    setSelectedSlug(docSlug)
    setQuery('')
    if (headingId) {
      // Vent til React har renderet det nye dokument, scroll derefter til overskriften
      setTimeout(() => {
        document.getElementById(headingId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 50)
    } else {
      setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 0)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-5">
        <h1 className="flex items-center gap-2 text-xl font-semibold text-gray-900">
          <LifeBuoy className="h-5 w-5 text-sky-500" />
          Hjælp &amp; dokumentation
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Vejledningerne følger den installerede version af TimeLapse Pro og virker også uden internetadgang.
        </p>
      </div>

      <div className="mb-5 relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Søg i hjælpen — fx 'backup', 'TOTP', 'LAB mode'…"
          aria-label="Søg i hjælpen"
          className="w-full rounded-lg border border-gray-300 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        />
      </div>

      {query.trim().length >= 2 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-800">
            {hits.length > 0 ? `${hits.length} resultat${hits.length === 1 ? '' : 'er'} for “${query.trim()}”` : `Ingen resultater for “${query.trim()}”`}
          </h2>
          <ul className="space-y-2">
            {hits.map((hit, idx) => (
              <li key={idx}>
                <button
                  onClick={() => goto(hit.doc.slug, hit.headingId || undefined)}
                  className="w-full rounded-lg border border-gray-100 px-3 py-2 text-left hover:border-sky-200 hover:bg-sky-50"
                >
                  <span className="block text-xs font-medium text-sky-700">
                    {hit.doc.title} · {hit.heading}
                  </span>
                  <span className="block truncate text-sm text-gray-600">{hit.snippet}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
          <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
            <nav aria-label="Hjælpedokumenter" className="rounded-xl border border-gray-200 bg-white p-2">
              {visibleDocs.map((doc) => {
                const Icon = doc.icon
                const active = doc.slug === selected.slug
                return (
                  <button
                    key={doc.slug}
                    onClick={() => goto(doc.slug)}
                    aria-current={active ? 'page' : undefined}
                    className={`flex w-full items-start gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors ${
                      active ? 'bg-sky-50 text-sky-900' : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <Icon className={`mt-0.5 h-4 w-4 flex-shrink-0 ${active ? 'text-sky-600' : 'text-gray-400'}`} />
                    <span>
                      <span className="block text-sm font-medium">{doc.title}</span>
                      <span className="block text-xs text-gray-500">{doc.description}</span>
                    </span>
                  </button>
                )
              })}
            </nav>

            {headings.length > 0 && (
              <nav aria-label="Indhold i valgte dokument" className="rounded-xl border border-gray-200 bg-white p-3">
                <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Indhold</p>
                <ul className="max-h-96 space-y-0.5 overflow-y-auto">
                  {headings
                    .filter((h) => h.level <= 3)
                    .map((h) => (
                      <li key={h.id}>
                        <button
                          onClick={() => goto(selected.slug, h.id)}
                          className={`w-full truncate rounded px-2 py-1 text-left text-xs text-gray-600 hover:bg-gray-50 hover:text-gray-900 ${
                            h.level === 1 ? 'font-semibold' : h.level === 2 ? 'pl-2' : 'pl-4 text-gray-500'
                          }`}
                          title={h.text}
                        >
                          {h.text}
                        </button>
                      </li>
                    ))}
                </ul>
              </nav>
            )}
          </aside>

          <article className="min-w-0 rounded-xl border border-gray-200 bg-white px-6 py-5">
            <Markdown source={selected.source} />
          </article>
        </div>
      )}
    </div>
  )
}
