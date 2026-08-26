import { Info } from 'lucide-react'

/**
 * InfoTooltip — lille ⓘ-ikon ved siden af labels, overskrifter og knapper,
 * der viser en kort forklaring (2-4 linjer) ved hover eller tastaturfokus.
 *
 * Skriv teksterne på dansk og hold dem i samme terminologi som menuguiderne
 * (Dokumentation/MENUGUIDE_BRUGER_v1.md og MENUGUIDE_ADMIN_v1.md), så
 * hover-hjælpen, hjælpesiden (/help) og manualerne siger det samme.
 *
 * Rent CSS (group-hover + focus-within) — ingen JavaScript-state, virker
 * derfor også på touch via fokus, og kan ikke fejle.
 */
export function InfoTooltip({ text, label = 'Forklaring' }: { text: string; label?: string }) {
  return (
    <span className="group/tt relative inline-flex items-center align-middle">
      <button
        type="button"
        tabIndex={0}
        aria-label={label}
        className="ml-1 inline-flex items-center rounded-full p-0.5 text-slate-400 transition-colors hover:text-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-400"
      >
        <Info className="h-3.5 w-3.5" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute left-1/2 top-full z-50 mt-1.5 w-72 max-w-xs -translate-x-1/2 whitespace-pre-line rounded-lg bg-slate-900 px-3 py-2 text-left text-xs font-normal leading-relaxed text-slate-100 opacity-0 shadow-xl ring-1 ring-slate-700 transition-opacity group-hover/tt:visible group-hover/tt:opacity-100 group-focus-within/tt:visible group-focus-within/tt:opacity-100"
      >
        {text}
      </span>
    </span>
  )
}
