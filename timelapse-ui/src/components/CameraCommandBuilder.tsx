// Command builder for the camera page's focus command fields; data from
// lib/cameraScan (the LAB "Hent parametre" scan).
import { useMemo, useState } from 'react'
import { leafOf, type CameraScan, type ScannedParam } from '../lib/cameraScan'

// Parameters most often used in focus commands come first in the builder.
const FOCUS_FIRST = ['liveviewaffocus', 'd0cd', 'viewfinder', 'autofocusdrive', 'manualfocusdrive', 'changeafarea', 'focusmode']

/**
 * Pick a camera parameter and one of its own values, append `name=value` to a
 * "k=v; k=v" command field — instead of guessing names and spellings.
 */
export function CommandBuilder({ scan, value, onChange }: {
  scan: CameraScan | null
  value: string
  onChange: (next: string) => void
}) {
  const writable = useMemo(() => {
    const rows = (scan?.params ?? []).filter(p => !p.readonly)
    const rank = (p: ScannedParam) => {
      const i = FOCUS_FIRST.indexOf(leafOf(p.path))
      return i === -1 ? FOCUS_FIRST.length : i
    }
    return [...rows].sort((a, b) => rank(a) - rank(b) || a.path.localeCompare(b.path))
  }, [scan])
  const [path, setPath] = useState('')
  const [choice, setChoice] = useState('')
  const param = writable.find(p => p.path === path)

  if (!scan || scan.params.length === 0) {
    return (
      <p className="text-[11px] text-amber-600 mt-1">
        Ingen kamerascanning endnu — tryk "Hent parametre" i LAB, så kan du vælge parameter og værdi her.
      </p>
    )
  }

  function add() {
    if (!param || choice === '') return
    const entry = `${leafOf(param.path)}=${choice}`
    const parts = value.split(';').map(s => s.trim()).filter(Boolean)
      .filter(s => s.split('=')[0].trim() !== leafOf(param.path))   // replace same key
    onChange([...parts, entry].join('; '))
    setChoice('')
  }

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-gray-400">Tilføj:</span>
      <select value={path} onChange={e => { setPath(e.target.value); setChoice('') }}
        className="border border-gray-200 rounded px-2 py-1 max-w-[18rem]">
        <option value="">Vælg kameraparameter…</option>
        {writable.map(p => (
          <option key={p.path} value={p.path}>{leafOf(p.path)} — {p.label}{p.current ? ` (nu: ${p.current})` : ''}</option>
        ))}
      </select>
      {param && (param.choices.length > 0 ? (
        <select value={choice} onChange={e => setChoice(e.target.value)} className="border border-gray-200 rounded px-2 py-1">
          <option value="">Vælg værdi…</option>
          {param.choices.map(c => <option key={c.index} value={c.label}>{c.label}{c.label === param.current ? ' ← nu' : ''}</option>)}
        </select>
      ) : param.type.toUpperCase() === 'TOGGLE' ? (
        <select value={choice} onChange={e => setChoice(e.target.value)} className="border border-gray-200 rounded px-2 py-1">
          <option value="">Vælg…</option><option value="1">1 (til)</option><option value="0">0 (fra)</option>
        </select>
      ) : (
        <input value={choice} onChange={e => setChoice(e.target.value)}
          type={param.bottom !== undefined ? 'number' : 'text'} min={param.bottom} max={param.top} step={param.step}
          placeholder={param.bottom !== undefined ? `${param.bottom} … ${param.top}` : 'værdi'}
          className="border border-gray-200 rounded px-2 py-1 w-36" />
      ))}
      <button type="button" onClick={add} disabled={!param || choice === ''}
        className="px-2 py-1 rounded bg-sky-600 text-white disabled:opacity-40">Tilføj</button>
    </div>
  )
}
