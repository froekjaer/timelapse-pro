// v5.1
import { useState, useMemo, useEffect, useRef } from 'react'
import { Trash2, X, Brain, Loader2, Search } from 'lucide-react'
import type { Capture } from '../types'
import { getApiUrl, deleteCapturesBulk, type CaptureDeletionReason } from '../api/client'
import { CaptureThumbnailCard } from './CaptureThumbnailCard'

function authFetch(url: string) {
  return fetch(url, { credentials: 'include' })
}

function authJson(path: string, body: unknown) {
  return fetch(`${getApiUrl()}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}



interface DayCount {
  year: number; month: number; day: number; count: number
}
interface Props {
  deviceId: string
  captures: Capture[]
  onSelect: (index: number) => void
  onDeleted?: () => void
}

const MONTHS = ['Jan','Feb','Mar','Apr','Maj','Jun','Jul','Aug','Sep','Okt','Nov','Dec']

export function TimelineNavigator({ deviceId, captures, onSelect, onDeleted }: Props) {
  const [dayCounts, setDayCounts]     = useState<DayCount[]>([])
  const [dayCaptures, setDayCaptures] = useState<Capture[]>([])
  const [selected, setSelected]       = useState<{ year?: number; month?: number; day?: number }>({})
  const [loading, setLoading]         = useState(false)
  const [, setSelFilename] = useState<string | null>(null)
  const [deleteMode, setDeleteMode]   = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [deleting, setDeleting]       = useState(false)
  const [deletionReason, setDeletionReason] = useState<CaptureDeletionReason>('defective')
  const [deletionDetails, setDeletionDetails] = useState('')
  const [naturalQuery, setNaturalQuery] = useState('')
  const [naturalNote, setNaturalNote] = useState('')
  const [naturalLoading, setNaturalLoading] = useState(false)
  const skipNextDayLoad = useRef(false)
  const queryDeviceId = encodeURIComponent(deviceId)

  useEffect(() => {
    if (!deviceId) return
    authFetch(`${getApiUrl()}/api/admin/captures/timeline?device_id=${encodeURIComponent(deviceId)}`)
      .then(r => r.json())
      .then((data: DayCount[]) => {
        setDayCounts(data)
        if (data.length > 0) {
          const last = data[data.length - 1]
          setSelected({ year: last.year, month: last.month, day: last.day })
        }
      }).catch(() => {})
  }, [deviceId])

  useEffect(() => {
    if (!selected.year || !selected.month || !selected.day) return
    if (skipNextDayLoad.current) {
      skipNextDayLoad.current = false
      return
    }
    setLoading(true)
    authFetch(`${getApiUrl()}/api/admin/captures/timeline?device_id=${queryDeviceId}&year=${selected.year}&month=${selected.month}&day=${selected.day}`)
      .then(r => r.json())
      .then((data: Capture[]) => { setDayCaptures(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [deviceId, selected.year, selected.month, selected.day])

  function normalizeNaturalCapture(item: any): Capture {
    return {
      id: item.id,
      device_id: item.device_id,
      filename: item.filename,
      captured_at: item.captured_at,
      quality_flag: item.quality?.flag ?? item.quality_flag ?? null,
      quality_passed: item.quality?.passed ?? item.quality_passed ?? null,
      blur_score: item.quality?.blur_score ?? item.blur_score ?? null,
      filesize_mb: item.filesize_mb ?? null,
      uploaded: item.uploaded ?? true,
      ai_result: item.ai_result ?? (item.ai ? JSON.stringify(item.ai) : null),
      ai_analyzed_at: item.ai?.analyzed_at ?? item.ai_analyzed_at ?? null,
      ai_tags: item.ai?.tags ?? item.ai_tags ?? null,
    }
  }

  async function handleNaturalSearch() {
    if (!naturalQuery.trim()) return
    setNaturalLoading(true)
    try {
      const data = await authJson('/api/ai/captures/natural-search', {
        query: naturalQuery,
        purpose: 'timeline',
        device_id: deviceId,
        limit: 200,
      })
      const results = (data.results ?? []).map(normalizeNaturalCapture)
      setDayCaptures(results)
      setNaturalNote(data.selection?.explanation || `${results.length} billeder matcher AI-søgningen`)
      if (results[0]?.captured_at) {
        const d = new Date(results[0].captured_at)
        skipNextDayLoad.current = true
        setSelected({ year: d.getFullYear(), month: d.getMonth() + 1, day: d.getDate() })
      }
    } catch {
      setNaturalNote('AI-søgning fejlede. Prøv en bredere formulering eller tjek Ollama-status.')
    } finally {
      setNaturalLoading(false)
    }
  }

  const yearIndex = useMemo(() => {
    const idx: Record<number, Record<number, DayCount[]>> = {}
    for (const dc of dayCounts) {
      if (!idx[dc.year]) idx[dc.year] = {}
      if (!idx[dc.year][dc.month]) idx[dc.year][dc.month] = []
      idx[dc.year][dc.month].push(dc)
    }
    return idx
  }, [dayCounts])

  const years  = Object.keys(yearIndex).map(Number).sort((a,b) => b-a)
  const months = selected.year ? Object.keys(yearIndex[selected.year] ?? {}).map(Number).sort((a,b) => b-a) : []
  const days   = (selected.year && selected.month) ? (yearIndex[selected.year]?.[selected.month] ?? []).sort((a,b) => b.day-a.day) : []
  const total  = dayCounts.reduce((s,d) => s+d.count, 0)

  function densityColor(count: number) {
    if (count === 0) return ''
    if (count < 5)   return 'bg-sky-100 text-gray-800'
    if (count < 20)  return 'bg-sky-200 text-gray-900'
    if (count < 50)  return 'bg-sky-400 text-white'
    return 'bg-sky-600 text-white'
  }

  function openCapture(c: Capture) {
    setSelFilename(c.filename)
    const idx = captures.findIndex(cap => cap.filename === c.filename)
    if (idx >= 0) {
      onSelect(idx)
    } else {
      // Billede ikke i hoved-listen — indsæt i captures og åbn
      // For nu: trigger med kunstigt index der signalerer "brug dayCaptures"
      captures.unshift(c)
      onSelect(0)
    }
  }

  async function handleBulkDelete() {
    if (selectedIds.size === 0) return
    if (!confirm(`Slet ${selectedIds.size} billeder? Dette kan ikke fortrydes.`)) return
    setDeleting(true)
    try {
      await deleteCapturesBulk([...selectedIds], deletionReason, deletionDetails)
      setSelectedIds(new Set())
      setDeleteMode(false)
      // Genindlæs dag-captures
      if (selected.year && selected.month && selected.day) {
        setLoading(true)
        authFetch(`${getApiUrl()}/api/admin/captures/timeline?device_id=${queryDeviceId}&year=${selected.year}&month=${selected.month}&day=${selected.day}`)
          .then(r => r.json()).then((data: Capture[]) => { setDayCaptures(data); setLoading(false) })
          .catch(() => setLoading(false))
        authFetch(`${getApiUrl()}/api/admin/captures/timeline?device_id=${queryDeviceId}`)
          .then(r => r.json()).then((data: DayCount[]) => setDayCounts(data)).catch(() => {})
      }
      onDeleted?.()
    } catch { alert('Sletning fejlede') }
    finally { setDeleting(false) }
  }

  function toggleSelect(id: number) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3 text-sm text-gray-400 flex-wrap">
        <span>{total.toLocaleString()} billeder totalt · {dayCounts.length} dage</span>
        {selected.year && selected.month && selected.day && (
          <span className="text-sky-600 font-medium">
            {selected.day}. {MONTHS[selected.month-1]} {selected.year} — {days.find(d => d.day === selected.day)?.count ?? 0} billeder
          </span>
        )}
        </div>
        <div className="flex items-center gap-2">
          {deleteMode && selectedIds.size > 0 && (
            <select value={deletionReason} onChange={e => setDeletionReason(e.target.value as CaptureDeletionReason)}
              aria-label="Årsag til sletning" className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white">
              <option value="defective">Defekt billede</option>
              <option value="unwanted">Uønsket billede</option>
              <option value="gdpr_request">GDPR-anmodning</option>
              <option value="other">Anden</option>
            </select>
          )}
          {deleteMode && selectedIds.size > 0 && deletionReason === 'other' && (
            <input value={deletionDetails} onChange={e => setDeletionDetails(e.target.value)}
              aria-label="Anden årsag" placeholder="Skriv konkret årsag" required minLength={3}
              className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm min-w-48" />
          )}
          {deleteMode && selectedIds.size > 0 && (
            <button onClick={handleBulkDelete} disabled={deleting || (deletionReason === 'other' && deletionDetails.trim().length < 3)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 disabled:opacity-50">
              <Trash2 className="w-3.5 h-3.5" />
              {deleting ? 'Sletter…' : `Slet ${selectedIds.size}`}
            </button>
          )}
          <button onClick={() => { setDeleteMode(m => !m); setSelectedIds(new Set()) }}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border transition-colors ${deleteMode ? 'bg-gray-100 border-gray-300 text-gray-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
            {deleteMode ? <X className="w-3.5 h-3.5" /> : <Trash2 className="w-3.5 h-3.5" />}
            {deleteMode ? 'Annuller' : 'Vælg til sletning'}
          </button>
        </div>
      </div>

      <div className="border border-sky-100 bg-sky-50 rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="w-4 h-4 text-sky-600" />
          <span className="text-sm font-medium text-sky-900">AI-søgning i timeline</span>
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-white border border-sky-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-sky-200"
            placeholder="f.eks. seneste skarpe billeder med byggeaktivitet uden regn"
            value={naturalQuery}
            onChange={e => setNaturalQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleNaturalSearch() }}
          />
          <button
            onClick={handleNaturalSearch}
            disabled={naturalLoading || !naturalQuery.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-sky-600 text-white text-sm rounded-lg disabled:opacity-40"
          >
            {naturalLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
            Find
          </button>
        </div>
        {naturalNote && <p className="text-xs text-sky-700 mt-2">{naturalNote}</p>}
      </div>

      {/* År */}
      <div className="flex gap-2 flex-wrap">
        {years.map(y => (
          <button key={y} onClick={() => { setNaturalNote(''); setSelected(s => ({ year: y, month: s.year===y ? s.month : undefined })) }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selected.year===y ? 'bg-sky-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {y} <span className={`ml-1 text-xs ${selected.year===y ? 'text-sky-200' : 'text-gray-400'}`}>
              {Object.values(yearIndex[y]??{}).flat().reduce((s,d)=>s+d.count,0)}
            </span>
          </button>
        ))}
      </div>

      {/* Måneder */}
      {selected.year && (
        <div className="flex gap-2 flex-wrap">
          {months.map(mo => {
            const count = (yearIndex[selected.year!]?.[mo]??[]).reduce((s,d)=>s+d.count,0)
            return (
              <button key={mo} onClick={() => { setNaturalNote(''); setSelected(s => ({...s, month: mo, day: undefined})) }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selected.month===mo ? 'bg-sky-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                {MONTHS[mo-1]} <span className={`ml-1 text-xs ${selected.month===mo ? 'text-sky-200' : 'text-gray-400'}`}>{count}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Dage kalender */}
      {selected.year && selected.month && (
        <div className="border border-gray-200 rounded-xl p-3 bg-white">
        <div className="grid grid-cols-7 gap-1">
          {['Man','Tir','Ons','Tor','Fre','Lør','Søn'].map(d => (
            <div key={d} className="text-center text-xs font-semibold text-gray-500 py-1">{d}</div>
          ))}
          {(() => {
            const firstDay  = new Date(selected.year!, selected.month!-1, 1).getDay()
            const offset    = firstDay === 0 ? 6 : firstDay-1
            const daysInMo  = new Date(selected.year!, selected.month!, 0).getDate()
            const cells = []
            for (let i=0; i<offset; i++) cells.push(<div key={`e${i}`} />)
            for (let d=1; d<=daysInMo; d++) {
              const dc    = days.find(x => x.day===d)
              const count = dc?.count ?? 0
              const isSel = selected.day === d
              cells.push(
                <button key={d} onClick={() => { if (count > 0) { setNaturalNote(''); setSelected(s=>({...s,day:d})) } }}
                  disabled={count===0}
                  className={`rounded text-xs font-semibold transition-all flex flex-col items-center justify-center gap-0.5 py-1.5 ${isSel ? 'ring-2 ring-sky-500 ring-offset-1' : ''} ${count>0 ? densityColor(count)+' hover:scale-105 cursor-pointer' : 'bg-transparent text-gray-300 cursor-default'}`}>
                  <span className={count > 0 ? '' : 'text-gray-300'}>{d}</span>
                  {count>0 && <span style={{fontSize:8}} className="opacity-80">{count}</span>}
                </button>
              )
            }
            return cells
          })()}
        </div>
        </div>
      )}

      {/* Dagens billeder */}
      {selected.day && (
        <div className="mt-4">
          {loading ? (
            <div className="text-center py-8 text-gray-400 text-sm">Indlæser billeder…</div>
          ) : dayCaptures.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">Ingen billeder</div>
          ) : (
            <>
              <p className="text-xs text-gray-400 mb-3">{dayCaptures.length} billeder</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {dayCaptures.map(c => {
                  return (
                    <CaptureThumbnailCard
                      key={c.id}
                      capture={c}
                      compact
                      selected={deleteMode && selectedIds.has(c.id)}
                      onClick={() => deleteMode ? toggleSelect(c.id) : openCapture(c)}
                      overlay={deleteMode && selectedIds.has(c.id) ? <div className="absolute inset-0 bg-red-400/20" /> : null}
                    />
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
