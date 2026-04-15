// v5.1
import { useState, useMemo, useEffect } from 'react'
import { ChevronLeft } from 'lucide-react'
import type { Capture } from '../types'
import { getThumbnailUrl, getApiUrl } from '../api/client'

interface DayCount {
  year: number; month: number; day: number; count: number
}
interface Props {
  deviceId: string
  captures: Capture[]
  onSelect: (index: number) => void
}

const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'
const MONTHS = ['Jan','Feb','Mar','Apr','Maj','Jun','Jul','Aug','Sep','Okt','Nov','Dec']

function toLocal(iso: string) {
  return new Date(new Date(iso + 'Z').toLocaleString('en-US', { timeZone: getTz() }))
}

export function TimelineNavigator({ deviceId, captures, onSelect }: Props) {
  const [dayCounts, setDayCounts]     = useState<DayCount[]>([])
  const [dayCaptures, setDayCaptures] = useState<Capture[]>([])
  const [selected, setSelected]       = useState<{ year?: number; month?: number; day?: number }>({})
  const [loading, setLoading]         = useState(false)
  const [selFilename, setSelFilename] = useState<string | null>(null)

  useEffect(() => {
    if (!deviceId) return
    fetch(`${getApiUrl()}/api/admin/captures/timeline?device_id=${deviceId}`)
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
    setLoading(true)
    fetch(`${getApiUrl()}/api/admin/captures/timeline?device_id=${deviceId}&year=${selected.year}&month=${selected.month}&day=${selected.day}`)
      .then(r => r.json())
      .then((data: Capture[]) => { setDayCaptures(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [deviceId, selected.year, selected.month, selected.day])

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

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 text-sm text-gray-400 flex-wrap">
        <span>{total.toLocaleString()} billeder totalt · {dayCounts.length} dage</span>
        {selected.year && selected.month && selected.day && (
          <span className="text-sky-600 font-medium">
            {selected.day}. {MONTHS[selected.month-1]} {selected.year} — {days.find(d => d.day === selected.day)?.count ?? 0} billeder
          </span>
        )}
      </div>

      {/* År */}
      <div className="flex gap-2 flex-wrap">
        {years.map(y => (
          <button key={y} onClick={() => setSelected(s => ({ year: y, month: s.year===y ? s.month : undefined }))}
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
              <button key={mo} onClick={() => setSelected(s => ({...s, month: mo, day: undefined}))}
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
                <button key={d} onClick={() => count>0 && setSelected(s=>({...s,day:d}))}
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
              <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-1.5">
                {dayCaptures.map(c => {
                  const d   = c.captured_at ? toLocal(c.captured_at) : null
                  const lbl = d ? `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}` : ''
                  return (
                    <button key={c.id} onClick={() => openCapture(c)}
                      className={`relative rounded-lg overflow-hidden border-2 transition-all hover:scale-105 ${selFilename===c.filename ? 'border-sky-400' : 'border-transparent'} ${!c.quality_passed ? 'ring-1 ring-red-400' : ''}`}>
                      <img src={getThumbnailUrl(c.device_id, c.filename)} alt="" className="w-full aspect-video object-cover" />
                      <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-center py-0.5" style={{fontSize:9}}>{lbl}</div>
                    </button>
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
