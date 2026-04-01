import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Capture } from '../types'
import { getThumbnailUrl } from '../api/client'

interface Props {
  captures: Capture[]
  onSelect: (index: number) => void
}

const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

function toLocal(iso: string) {
  return new Date(new Date(iso + 'Z').toLocaleString('en-US', { timeZone: getTz() }))
}

export function TimelineNavigator({ captures, onSelect }: Props) {
  const nowDate = new Date()
  const [view, setView] = useState<'year' | 'month' | 'day' | 'hour'>('day')
  const [selected, setSelected] = useState<{ year?: number; month?: number; day?: number }>(() => {
    const y = nowDate.getFullYear()
    const mo = nowDate.getMonth() + 1
    return { year: y, month: mo }
  })

  // Build index: year → month → day → hour → captures[]
  const index = useMemo(() => {
    const idx: Record<number, Record<number, Record<number, Record<number, Capture[]>>>> = {}
    for (const c of captures) {
      if (!c.captured_at) continue
      const d = toLocal(c.captured_at)
      const y = d.getFullYear(), mo = d.getMonth() + 1, dd = d.getDate(), h = d.getHours()
      if (!idx[y]) idx[y] = {}
      if (!idx[y][mo]) idx[y][mo] = {}
      if (!idx[y][mo][dd]) idx[y][mo][dd] = {}
      if (!idx[y][mo][dd][h]) idx[y][mo][dd][h] = []
      idx[y][mo][dd][h].push(c)
    }
    return idx
  }, [captures])

  const years  = Object.keys(index).map(Number).sort()
  const months = selected.year ? Object.keys(index[selected.year] ?? {}).map(Number).sort() : []
  const days   = (selected.year && selected.month) ? Object.keys(index[selected.year]?.[selected.month] ?? {}).map(Number).sort() : []
  const hours  = (selected.year && selected.month && selected.day)
    ? Object.keys(index[selected.year]?.[selected.month]?.[selected.day] ?? {}).map(Number).sort()
    : []

  const countForDay = (y: number, mo: number, d: number) =>
    Object.values(index[y]?.[mo]?.[d] ?? {}).flat().length

  const countForHour = (y: number, mo: number, d: number, h: number) =>
    (index[y]?.[mo]?.[d]?.[h] ?? []).length

  const monthNames = ['Jan','Feb','Mar','Apr','Maj','Jun','Jul','Aug','Sep','Okt','Nov','Dec']

  const densityColor = (count: number, max: number) => {
    if (count === 0) return 'bg-gray-100 text-gray-300'
    const pct = count / max
    if (pct > 0.7) return 'bg-sky-500 text-white'
    if (pct > 0.3) return 'bg-sky-300 text-sky-900'
    return 'bg-sky-100 text-sky-700'
  }

  const Cell = ({ label, count, max, onClick, active }: { label: string; count: number; max: number; onClick: () => void; active?: boolean }) => (
    <button
      onClick={onClick}
      className={`rounded-lg p-2 text-center transition-all hover:ring-2 hover:ring-sky-400 ${
        active ? 'ring-2 ring-sky-500 ' : ''
      }${densityColor(count, max)}`}
    >
      <p className="text-xs font-medium">{label}</p>
      {count > 0 && <p className="text-xs opacity-70 mt-0.5">{count}</p>}
    </button>
  )

  // Selected hour thumbnails — 5 before + 5 after
  const selectedCaptures = useMemo(() => {
    if (!selected.year || !selected.month || !selected.day) return []
    if (view !== 'hour') return []
    return [] // shown below
  }, [selected, view])

  const hourCaptures = (selected.year && selected.month && selected.day)
    ? Object.entries(index[selected.year]?.[selected.month]?.[selected.day] ?? {})
        .sort(([a], [b]) => Number(a) - Number(b))
        .flatMap(([, caps]) => caps)
    : []

  const globalMax = Math.max(...Object.values(index).flatMap(mo =>
    Object.values(mo).flatMap(dd => Object.values(dd).flatMap(hh => Object.values(hh).map(c => c.length)))
  ), 1)

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center gap-2 mb-4">
          {view !== 'year' && (
            <button
              onClick={() => {
                if (view === 'month') { setView('year'); setSelected({}) }
                if (view === 'day')   { setView('month'); setSelected(s => ({ year: s.year })) }
                if (view === 'hour')  { setView('day'); setSelected(s => ({ year: s.year, month: s.month })) }
              }}
              className="p-1 rounded hover:bg-gray-100"
            >
              <ChevronLeft className="w-4 h-4 text-gray-500" />
            </button>
          )}
          <h3 className="text-sm font-semibold text-gray-800">
            {view === 'year'  && 'Vælg år'}
            {view === 'month' && `${selected.year ?? new Date().getFullYear()} — vælg måned`}
            {view === 'day'   && `${monthNames[(selected.month ?? 1) - 1]} ${selected.year} — vælg dag`}
            {view === 'hour'  && `${selected.day}. ${monthNames[(selected.month ?? 1) - 1]} ${selected.year} — vælg time`}
          </h3>
        </div>

        {view === 'year' && (
          <div className="grid grid-cols-4 gap-2">
            {years.map(y => {
              const total = Object.values(index[y]).flatMap(mo => Object.values(mo).flatMap(dd => Object.values(dd).flat())).length
              return <Cell key={y} label={String(y)} count={total} max={globalMax * 30} onClick={() => { setSelected({ year: y }); setView('month') }} />
            })}
          </div>
        )}

        {view === 'month' && selected.year && (
          <div className="grid grid-cols-4 gap-2">
            {monthNames.map((name, i) => {
              const mo = i + 1
              const count = months.includes(mo)
                ? Object.values(index[selected.year!]?.[mo] ?? {}).flatMap(dd => Object.values(dd).flat()).length
                : 0
              return (
                <Cell key={mo} label={name} count={count} max={globalMax * 10}
                  onClick={() => { if (count > 0) { setSelected(s => ({ ...s, month: mo })); setView('day') } }}
                />
              )
            })}
          </div>
        )}

        {view === 'day' && selected.year && selected.month && (
          <div className="grid grid-cols-7 gap-1.5">
            {['Ma','Ti','On','To','Fr','Lø','Sø'].map(d => (
              <div key={d} className="text-center text-xs text-gray-400 pb-1">{d}</div>
            ))}
            {(() => {
              const firstDay = new Date(selected.year!, selected.month! - 1, 1).getDay()
              const offset = (firstDay + 6) % 7
              const daysInMonth = new Date(selected.year!, selected.month!, 0).getDate()
              const maxDay = Math.max(...days.map(d => countForDay(selected.year!, selected.month!, d)), 1)
              const cells = []
              for (let i = 0; i < offset; i++) cells.push(<div key={`e${i}`} />)
              for (let d = 1; d <= daysInMonth; d++) {
                const count = countForDay(selected.year!, selected.month!, d)
                cells.push(
                  <Cell key={d} label={String(d)} count={count} max={maxDay}
                    active={selected.day === d}
                    onClick={() => { if (count > 0) { setSelected(s => ({ ...s, day: d })); setView('hour') } }}
                  />
                )
              }
              return cells
            })()}
          </div>
        )}

        {view === 'hour' && selected.year && selected.month && selected.day && (
          <div className="grid grid-cols-6 gap-2">
            {Array.from({ length: 24 }, (_, h) => {
              const count = countForHour(selected.year!, selected.month!, selected.day!, h)
              return (
                <Cell key={h} label={`${String(h).padStart(2,'0')}:00`} count={count} max={6}
                  onClick={() => {
                    if (count > 0) {
                      const caps = index[selected.year!]?.[selected.month!]?.[selected.day!]?.[h] ?? []
                      if (caps.length > 0) {
                        const globalIdx = captures.findIndex(c => c.id === caps[0].id)
                        if (globalIdx >= 0) onSelect(globalIdx)
                      }
                    }
                  }}
                />
              )
            })}
          </div>
        )}
      </div>

      {view === 'hour' && selected.year && selected.month && selected.day && hourCaptures.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-400 mb-3">{hourCaptures.length} billeder denne dag</p>
          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
            {hourCaptures.map((c, i) => {
              const globalIdx = captures.findIndex(cap => cap.id === c.id)
              const time = c.captured_at
                ? new Date(c.captured_at + 'Z').toLocaleTimeString('da-DK', { timeZone: getTz(), hour: '2-digit', minute: '2-digit' })
                : '–'
              return (
                <button key={c.id} onClick={() => onSelect(globalIdx)}
                  className="rounded-lg overflow-hidden border border-gray-200 hover:ring-2 hover:ring-sky-400 transition-all"
                >
                  <div className="aspect-video bg-slate-100 overflow-hidden">
                    <img src={getThumbnailUrl(c.device_id, c.filename)} alt="" className="w-full h-full object-cover" loading="lazy" />
                  </div>
                  <p className="text-xs text-center text-gray-500 py-1">{time}</p>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
