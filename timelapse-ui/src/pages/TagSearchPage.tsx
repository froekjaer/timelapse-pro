// TimeLapse Pro — TagSearchPage.tsx v4
// ======================================
// Filtre baseret på customer_name/site_name fra device-listen.
// Viser total matches uanset visningsbegrænsning.
// Klik på billede åbner fuld Lightbox.

import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Tag, Search, X, Loader2, CheckSquare, Square,
         Save, FlaskConical, ChevronDown, ChevronUp, Brain } from 'lucide-react'
import { getApiUrl } from '../api/client'
import { Lightbox } from './DevicePage'
import { CaptureThumbnailCard } from '../components/CaptureThumbnailCard'
import { useTagLabels, tagLabel } from '../hooks/useTagLabels'
import type { Capture } from '../types'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' }, ...opts
  }).then((r: Response) => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

// ── Multi-select dropdown ─────────────────────────────────────────────────────

function MultiSelect({ label, options, selected, onChange, disabled }: {
  label: string
  options: { value: string; label: string }[]
  selected: string[]
  onChange: (v: string[]) => void
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)

  function toggle(v: string) {
    onChange(selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v])
  }

  const display = selected.length === 0
    ? `Alle ${label}`
    : selected.length === 1
      ? (options.find(o => o.value === selected[0])?.label ?? selected[0])
      : `${selected.length} valgt`

  if (disabled || options.length === 0) return (
    <div className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-400 bg-gray-50">
      {options.length === 0 ? `Ingen ${label}` : `Alle ${label}`}
    </div>
  )

  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center justify-between border rounded-lg px-3 py-1.5 text-sm text-left transition-colors ${
          selected.length > 0 ? 'border-sky-300 bg-sky-50 text-sky-700' : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
        }`}>
        <span className="truncate">{display}</span>
        {open ? <ChevronUp className="w-3.5 h-3.5 flex-shrink-0 ml-1"/> : <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 ml-1"/>}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-20 min-w-[200px] max-h-64 overflow-y-auto">
            <div className="p-1.5">
              {selected.length > 0 && (
                <button onClick={() => { onChange([]); setOpen(false) }}
                  className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-50 rounded-lg mb-1">
                  Ryd alle
                </button>
              )}
              {options.map(opt => (
                <button key={opt.value} onClick={() => toggle(opt.value)}
                  className="w-full flex items-center gap-2.5 px-3 py-1.5 text-sm hover:bg-gray-50 rounded-lg">
                  {selected.includes(opt.value)
                    ? <CheckSquare className="w-4 h-4 text-sky-500 flex-shrink-0"/>
                    : <Square className="w-4 h-4 text-gray-300 flex-shrink-0"/>}
                  <span className="truncate">{opt.label}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Tag editor ────────────────────────────────────────────────────────────────

function TagEditor({ captureIds, allTags, currentTags, onSave, onClose }: {
  captureIds: number[]; allTags: string[]; currentTags: string[]
  onSave: (a: string[], r: string[]) => Promise<void>; onClose: () => void
}) {
  const [addInput, setAddInput] = useState('')
  const [addTags, setAddTags]   = useState<string[]>([])
  const [removeTags, setRemoveTags] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const sugg = allTags.filter(t => t.includes(addInput.toLowerCase()) && !addTags.includes(t)).slice(0, 6)
  const addTag = (t: string) => { const tag = t.trim().toLowerCase().replace(/^#/,''); if(tag&&!addTags.includes(tag)) setAddTags(p=>[...p,tag]); setAddInput('') }
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Rediger tags — {captureIds.length} billede{captureIds.length!==1?'r':''}</h3>
          <button onClick={onClose}><X className="w-5 h-5 text-gray-400"/></button>
        </div>
        <div className="mb-4">
          <label className="text-xs font-medium text-gray-600 block mb-1.5">Tilføj tags</label>
          <div className="flex flex-wrap gap-1 mb-2">
            {addTags.map(t=><span key={t} className="inline-flex items-center gap-1 bg-sky-100 text-sky-700 text-xs px-2 py-0.5 rounded-full">#{t}<button onClick={()=>setAddTags(p=>p.filter(x=>x!==t))}><X className="w-3 h-3"/></button></span>)}
          </div>
          <div className="relative">
            <input className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
              placeholder="Skriv tag og tryk Enter…" value={addInput}
              onChange={e=>setAddInput(e.target.value)}
              onKeyDown={e=>e.key==='Enter'&&addInput&&(addTag(addInput),e.preventDefault())}/>
            {addInput&&sugg.length>0&&<div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-10">{sugg.map(t=><button key={t} onMouseDown={()=>addTag(t)} className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50">#{t}</button>)}</div>}
          </div>
        </div>
        {currentTags.length>0&&<div className="mb-4"><label className="text-xs font-medium text-gray-600 block mb-1.5">Fjern tags</label><div className="flex flex-wrap gap-1.5">{currentTags.map(t=><button key={t} onClick={()=>setRemoveTags(p=>p.includes(t)?p.filter(x=>x!==t):[...p,t])} className={`text-xs px-2 py-0.5 rounded-full border ${removeTags.includes(t)?'bg-red-100 text-red-600 border-red-300 line-through':'bg-gray-100 text-gray-600 border-gray-200'}`}>#{t}</button>)}</div></div>}
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 px-4 py-2 border border-gray-200 text-sm rounded-lg">Annuller</button>
          <button onClick={async()=>{setSaving(true);await onSave(addTags,removeTags);setSaving(false)}} disabled={saving||(!addTags.length&&!removeTags.length)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg disabled:opacity-40">
            {saving?<Loader2 className="w-4 h-4 animate-spin"/>:<Save className="w-4 h-4"/>}{saving?'Gemmer…':'Gem'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Konstanter ────────────────────────────────────────────────────────────────

const QA_CAUSES = [
  { value: 'ok',                   label: '✓ OK' },
  { value: 'condensation_on_lens', label: '💧 Kondens på linse' },
  { value: 'dirty_lens',           label: '🔍 Snavset linse' },
  { value: 'focus_drift',          label: '🔭 Fokusdrift' },
  { value: 'camera_moved',         label: '📷 Kamera flyttet' },
  { value: 'obstruction',          label: '🚧 Afskærmning' },
  { value: 'rain_on_lens',         label: '🌧 Regn på linse' },
  { value: 'sun_flare',            label: '☀️ Solreflektion' },
  { value: 'night_capture',        label: '🌙 Natkamera' },
  { value: 'hardware_failure',     label: '⚠️ Hardwarefejl' },
  { value: 'unknown',              label: '❓ Ukendt' },
]

const DISPLAY_LIMIT = 200  // Antal billeder der vises — søgningen finder alle

// ── Hoved-komponent ───────────────────────────────────────────────────────────

interface DeviceInfo { device_id: string; camera_name?: string; customer_name?: string; site_name?: string }

export function TagSearchPage() {
  const tagLabels = useTagLabels()
  const [mode, setMode] = useState<'tags' | 'qa' | 'natural'>('tags')

  // Tag søgning
  const [searchTags, setSearchTags] = useState<string[]>([])
  const [allTags, setAllTags]       = useState<{ tag: string; count: number }[]>([])
  const [tagInput, setTagInput]     = useState('')

  // QA søgning
  const [qaCauses, setQaCauses]   = useState<string[]>([])
  const [qaAnomaly, setQaAnomaly] = useState<string[]>([])
  const [qaAlarm, setQaAlarm]     = useState<string[]>([])
  const [qaMinConf, setQaMinConf] = useState('')

  // Naturlig AI søgning
  const [naturalQuery, setNaturalQuery] = useState('')
  const [naturalNote, setNaturalNote] = useState('')

  // Fælles filtre
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo]     = useState('')

  // Devices + hierarkisk filter
  const [allDevices, setAllDevices]       = useState<DeviceInfo[]>([])
  const [selCustomers, setSelCustomers]   = useState<string[]>([])
  const [selSites, setSelSites]           = useState<string[]>([])
  const [selDeviceIds, setSelDeviceIds]   = useState<string[]>([])

  // Resultater
  const [allResults, setAllResults]       = useState<any[]>([])  // Alle matches
  const [totalMatches, setTotalMatches]   = useState(0)
  const [loading, setLoading]             = useState(false)
  const [searched, setSearched]           = useState(false)
  const [selectedIds, setSelectedIds]     = useState<Set<number>>(new Set())
  const [lightboxIdx, setLightboxIdx]     = useState<number | null>(null)
  const [showEditor, setShowEditor]       = useState(false)

  useEffect(() => {
    api('/api/ai/tags/all').then((d: any) => setAllTags(d.tags ?? [])).catch(() => {})
    api('/api/admin/devices').then((d: any) => setAllDevices(d.devices ?? d ?? [])).catch(() => {})
  }, [])

  // Udled kunder/sites fra device-listen
  const customerOptions = useMemo(() => {
    const names = [...new Set(allDevices.map(d => d.customer_name).filter(Boolean))] as string[]
    return names.map(n => ({ value: n, label: n }))
  }, [allDevices])

  const siteOptions = useMemo(() => {
    const filtered = selCustomers.length > 0
      ? allDevices.filter(d => d.customer_name && selCustomers.includes(d.customer_name))
      : allDevices
    const names = [...new Set(filtered.map(d => d.site_name).filter(Boolean))] as string[]
    return names.map(n => ({ value: n, label: n }))
  }, [allDevices, selCustomers])

  // Når customer ændres, ryd site og device valg der ikke passer
  useEffect(() => {
    setSelSites(prev => prev.filter(s => siteOptions.some(o => o.value === s)))
  }, [selCustomers])

  const deviceOptions = useMemo(() => {
    let devs = allDevices
    if (selCustomers.length > 0) devs = devs.filter(d => d.customer_name && selCustomers.includes(d.customer_name))
    if (selSites.length > 0)     devs = devs.filter(d => d.site_name && selSites.includes(d.site_name))
    return devs.map(d => ({ value: d.device_id, label: d.camera_name || d.device_id }))
  }, [allDevices, selCustomers, selSites])

  // Udregn effektive device_ids baseret på filtre
  const effectiveDeviceIds = useMemo((): string[] => {
    if (selDeviceIds.length > 0) return selDeviceIds
    if (selSites.length > 0 || selCustomers.length > 0) return deviceOptions.map(o => o.value)
    return []
  }, [selDeviceIds, selSites, selCustomers, deviceOptions])

  // Tag suggestions
  const tagSugg = allTags.filter(t => t.tag.includes(tagInput.toLowerCase()) && !searchTags.includes(t.tag)).slice(0, 8)
  function addTag(t: string) { const tag = t.trim().toLowerCase().replace(/^#/,''); if(tag&&!searchTags.includes(tag)) setSearchTags(p=>[...p,tag]); setTagInput('') }
  function removeTag(t: string) { setSearchTags(p => p.filter(x => x !== t)) }

  function normalizeNaturalResult(item: any) {
    return {
      id: item.id,
      device_id: item.device_id,
      filename: item.filename,
      captured_at: item.captured_at,
      quality_passed: item.quality?.passed ?? item.quality_passed ?? null,
      quality_flag: item.quality?.flag ?? item.quality_flag ?? null,
      blur_score: item.quality?.blur_score ?? item.blur_score ?? null,
      brightness: item.quality?.brightness ?? item.brightness ?? null,
      filesize_mb: item.filesize_mb ?? null,
      uploaded: item.uploaded ?? true,
      ai_result: item.ai_result ?? (item.ai ? JSON.stringify(item.ai) : null),
      ai_analyzed_at: item.ai?.analyzed_at ?? item.ai_analyzed_at ?? null,
      ai_tags: item.ai?.tags ?? item.ai_tags ?? item.tags ?? null,
      tags: item.ai?.tags ?? item.ai_tags ?? item.tags ?? null,
    }
  }

  async function search() {
    setLoading(true); setSearched(true); setSelectedIds(new Set())
    try {
      let url: string
      const devParam = effectiveDeviceIds.length > 0 ? `&device_ids=${effectiveDeviceIds.join(',')}` : ''
      const dateParam = `${dateFrom ? `&date_from=${dateFrom}` : ''}${dateTo ? `&date_to=${dateTo}` : ''}`

      if (mode === 'natural') {
        const d: any = await api('/api/ai/captures/natural-search', {
          method: 'POST',
          body: JSON.stringify({
            query: naturalQuery,
            purpose: 'tag_search',
            device_ids: effectiveDeviceIds,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            limit: 500,
          }),
        })
        const results = (d.results ?? []).map(normalizeNaturalResult)
        setAllResults(results)
        setTotalMatches(d.total_matches ?? results.length)
        const spec = d.selection ?? {}
        setNaturalNote(spec.explanation || `AI-filter: ${[...(spec.include_tags ?? []).map((t: string) => `#${tagLabel(t, tagLabels)}`), ...(spec.exclude_tags ?? []).map((t: string) => `uden #${tagLabel(t, tagLabels)}`)].join(', ') || 'ingen tagfilter'}`)
        setLoading(false)
        return
      } else if (mode === 'tags') {
        if (searchTags.length === 0) { setLoading(false); return }
        url = `/api/ai/tags/search?tags=${searchTags.join(',')}&limit=5000${devParam}${dateParam}`
      } else {
        url = `/api/ai/qa/search?limit=5000${devParam}${dateParam}`
        if (qaCauses.length)  url += `&causes=${qaCauses.join(',')}`
        if (qaAnomaly.length) url += `&is_anomaly=${qaAnomaly[0]}`
        if (qaAlarm.length)   url += `&alarm=${qaAlarm[0]}`
        if (qaMinConf)        url += `&min_confidence=${qaMinConf}`
      }

      const d: any = await api(url)
      const results = d.results ?? []
      setAllResults(results)
      setTotalMatches(results.length)
    } catch { setAllResults([]); setTotalMatches(0) }
    setLoading(false)
  }

  // Vis kun første DISPLAY_LIMIT resultater
  const displayedResults = allResults.slice(0, DISPLAY_LIMIT)

  function toggleSelect(id: number) {
    setSelectedIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n })
  }

  async function saveTags(addT: string[], removeT: string[]) {
    await api('/api/captures/bulk-tags', {
      method: 'POST',
      body: JSON.stringify({ capture_ids: Array.from(selectedIds), add_tags: addT, remove_tags: removeT }),
    })
    setAllResults(prev => prev.map(r => {
      if (!selectedIds.has(r.id)) return r
      let tags = [...(r.tags ?? r.ai_tags ?? [])]
      tags = [...new Set([...tags, ...addT])].filter(t => !removeT.includes(t))
      return { ...r, tags, ai_tags: tags }
    }))
    setShowEditor(false)
  }

  const capturesForLightbox: Capture[] = displayedResults.map(r => ({
    id: r.id, device_id: r.device_id, filename: r.filename,
    captured_at: r.captured_at, quality_flag: r.quality_flag ?? null,
    quality_passed: r.quality_passed ?? null, blur_score: r.blur_score ?? null,
    filesize_mb: r.filesize_mb ?? null, uploaded: r.uploaded ?? true,
    ai_result: r.ai_result ?? null, ai_analyzed_at: r.ai_analyzed_at ?? null,
    ai_tags: r.ai_tags ?? r.tags ?? null,
  }))

  const commonTags = displayedResults.filter(r => selectedIds.has(r.id)).length > 0
    ? ((displayedResults.find(r => selectedIds.has(r.id))?.tags ?? displayedResults.find(r => selectedIds.has(r.id))?.ai_tags) ?? [])
        .filter((t: string) => displayedResults.filter(r => selectedIds.has(r.id)).every(c => [...(c.tags??[]),...(c.ai_tags??[])].includes(t)))
    : []

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {lightboxIdx !== null && (
        <Lightbox captures={capturesForLightbox} index={lightboxIdx} onClose={() => setLightboxIdx(null)} />
      )}

      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-gray-400 hover:text-gray-600"><ArrowLeft className="w-5 h-5"/></Link>
        <Tag className="w-5 h-5 text-sky-500"/>
        <h1 className="text-xl font-semibold text-gray-900">Søg i billeder</h1>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
        {[
          {id:'tags',label:'Tag søgning',icon:<Tag className="w-4 h-4"/>},
          {id:'qa',label:'QA søgning',icon:<FlaskConical className="w-4 h-4"/>},
          {id:'natural',label:'AI søgning',icon:<Brain className="w-4 h-4"/>},
        ].map(m=>(
          <button key={m.id} onClick={()=>setMode(m.id as any)}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors ${mode===m.id?'bg-white shadow text-sky-600 font-medium':'text-gray-500 hover:text-gray-700'}`}>
            {m.icon}{m.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-5 mb-6 space-y-4">

        {/* TAG MODE */}
        {mode === 'tags' && (
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">Tags</label>
            <div className="flex flex-wrap gap-1.5 p-2 border border-gray-200 rounded-xl min-h-[42px] bg-white">
              {searchTags.map(t=>(
                <span key={t} className="inline-flex items-center gap-1 bg-sky-100 text-sky-700 text-xs px-2 py-0.5 rounded-full">
                  #{t}<button onClick={()=>removeTag(t)}><X className="w-3 h-3"/></button>
                </span>
              ))}
              <div className="relative flex-1 min-w-[140px]">
                <input className="w-full outline-none text-sm bg-transparent"
                  placeholder="Skriv tag og tryk Enter…" value={tagInput}
                  onChange={e=>setTagInput(e.target.value)}
                  onKeyDown={e=>{if(e.key==='Enter'&&tagInput){addTag(tagInput);e.preventDefault()}if(e.key==='Backspace'&&!tagInput&&searchTags.length)removeTag(searchTags[searchTags.length-1])}}/>
                {tagInput&&tagSugg.length>0&&(
                  <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-20 min-w-[200px]">
                    {tagSugg.map(t=><button key={t.tag} onMouseDown={()=>addTag(t.tag)} className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex justify-between"><span>#{t.tag}</span><span className="text-gray-400 text-xs">{t.count}</span></button>)}
                  </div>
                )}
              </div>
            </div>
            {/* Tag cloud — altid synlig, valgte = blå */}
            <div className="mt-2 flex flex-wrap gap-1.5">
              {allTags.slice(0, 50).map(t=>(
                <button key={t.tag} onClick={()=>searchTags.includes(t.tag)?removeTag(t.tag):addTag(t.tag)}
                  className={`text-xs px-2 py-0.5 rounded-full transition-colors ${searchTags.includes(t.tag)?'bg-sky-500 text-white':'bg-gray-100 hover:bg-sky-100 hover:text-sky-700 text-gray-600'}`}>
                  #{t.tag} <span className="opacity-60">{t.count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* NATURAL MODE */}
        {mode === 'natural' && (
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">Spørg med almindeligt sprog</label>
            <div className="flex gap-2">
              <input
                className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm"
                placeholder="f.eks. find skarpe billeder med kran uden regn fra i dag"
                value={naturalQuery}
                onChange={e => setNaturalQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && naturalQuery.trim()) search() }}
              />
            </div>
            {naturalNote && (
              <p className="text-xs text-sky-700 bg-sky-50 border border-sky-100 rounded-lg px-3 py-2 mt-2">
                {naturalNote}
              </p>
            )}
          </div>
        )}

        {/* QA MODE */}
        {mode === 'qa' && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div><label className="text-xs font-medium text-gray-600 block mb-1.5">QA årsag</label>
              <MultiSelect label="årsager" options={QA_CAUSES} selected={qaCauses} onChange={setQaCauses}/></div>
            <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Anomali</label>
              <MultiSelect label="status" options={[{value:'true',label:'⚠️ Er anomali'},{value:'false',label:'✓ Normal'}]} selected={qaAnomaly} onChange={setQaAnomaly}/></div>
            <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Alarm</label>
              <MultiSelect label="alarm" options={[{value:'true',label:'🚨 Alarm udløst'},{value:'false',label:'Ingen alarm'}]} selected={qaAlarm} onChange={setQaAlarm}/></div>
            <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Min. konfidence</label>
              <input type="number" min="0" max="1" step="0.05" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" placeholder="f.eks. 0.7" value={qaMinConf} onChange={e=>setQaMinConf(e.target.value)}/></div>
          </div>
        )}

        {/* Fælles filtre */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-3 border-t border-gray-100">
          <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Fra dato</label>
            <input type="date" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" value={dateFrom} onChange={e=>setDateFrom(e.target.value)}/></div>
          <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Til dato</label>
            <input type="date" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" value={dateTo} onChange={e=>setDateTo(e.target.value)}/></div>
          <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Kunder</label>
            <MultiSelect label="kunder" options={customerOptions} selected={selCustomers} onChange={v=>{setSelCustomers(v);setSelSites([]);setSelDeviceIds([])}}/></div>
          <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Sites</label>
            <MultiSelect label="sites" options={siteOptions} selected={selSites} onChange={v=>{setSelSites(v);setSelDeviceIds([])}} disabled={siteOptions.length===0}/></div>
          <div><label className="text-xs font-medium text-gray-600 block mb-1.5">Kameraer</label>
            <MultiSelect label="kameraer" options={deviceOptions} selected={selDeviceIds} onChange={setSelDeviceIds} disabled={deviceOptions.length===0}/></div>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={search} disabled={loading||(mode==='tags'&&searchTags.length===0)||(mode==='natural'&&!naturalQuery.trim())}
            className="flex items-center gap-2 px-5 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-40">
            {loading?<Loader2 className="w-4 h-4 animate-spin"/>:<Search className="w-4 h-4"/>}Søg
          </button>
          {effectiveDeviceIds.length > 0 && (
            <span className="text-xs text-gray-400">{effectiveDeviceIds.length} kamera{effectiveDeviceIds.length!==1?'er':''} valgt</span>
          )}
        </div>
      </div>

      {/* Resultater */}
      {searched && (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3 flex-wrap">
              {loading ? (
                <p className="text-sm text-gray-500">Søger…</p>
              ) : (
                <>
                  <p className="text-sm text-gray-700 font-medium">
                    {totalMatches.toLocaleString('da-DK')} billeder fundet
                    {totalMatches > DISPLAY_LIMIT && (
                      <span className="text-gray-400 font-normal"> — viser de første {DISPLAY_LIMIT}</span>
                    )}
                  </p>
                  {displayedResults.length > 0 && (
                    <button onClick={() => setSelectedIds(s => s.size===displayedResults.length ? new Set() : new Set(displayedResults.map(r=>r.id)))}
                      className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 px-2.5 py-1 rounded-lg hover:bg-gray-50">
                      {selectedIds.size===displayedResults.length?<CheckSquare className="w-3.5 h-3.5 text-sky-500"/>:<Square className="w-3.5 h-3.5"/>}
                      {selectedIds.size===displayedResults.length?'Fravælg alle':'Vælg alle'}
                    </button>
                  )}
                </>
              )}
            </div>
            {selectedIds.size > 0 && (
              <button onClick={()=>setShowEditor(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600">
                <Tag className="w-3.5 h-3.5"/>Rediger tags ({selectedIds.size})
              </button>
            )}
          </div>

          {loading ? (
            <div className="py-20 text-center text-gray-400"><Loader2 className="w-8 h-8 animate-spin mx-auto mb-2"/>Søger…</div>
          ) : displayedResults.length === 0 ? (
            <div className="py-20 text-center text-gray-400"><Search className="w-12 h-12 mx-auto mb-3 opacity-30"/><p>Ingen billeder fundet</p></div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {displayedResults.map((r, i) => (
                  <div key={r.id} className="relative">
                    <button onClick={e=>{e.stopPropagation();toggleSelect(r.id)}}
                      className="absolute top-1.5 left-1.5 z-10 bg-white/80 rounded backdrop-blur-sm p-0.5">
                      {selectedIds.has(r.id)?<CheckSquare className="w-4 h-4 text-sky-500"/>:<Square className="w-4 h-4 text-gray-400"/>}
                    </button>
                    <CaptureThumbnailCard capture={r} onClick={()=>setLightboxIdx(i)}/>
                  </div>
                ))}
              </div>
              {totalMatches > DISPLAY_LIMIT && (
                <p className="text-center text-sm text-gray-400 mt-6 py-4 border-t border-gray-100">
                  Viser {DISPLAY_LIMIT} af {totalMatches.toLocaleString('da-DK')} billeder — præciser søgningen for at se specifikke resultater
                </p>
              )}
            </>
          )}
        </>
      )}

      {showEditor && (
        <TagEditor captureIds={Array.from(selectedIds)} allTags={allTags.map(t=>t.tag)}
          currentTags={commonTags} onSave={saveTags} onClose={()=>setShowEditor(false)}/>
      )}
    </div>
  )
}
