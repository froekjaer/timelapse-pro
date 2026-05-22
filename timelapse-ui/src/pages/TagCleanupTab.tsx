// TimeLapse Pro — TagCleanupTab.tsx
// Drag-and-drop tag oprydning med AI-gruppeforslag via Gemini

import { useEffect, useState, useCallback } from 'react'
import { Brain, RefreshCw, Plus, Trash2, Check, Archive, Square, CheckSquare } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface TagItem  { id: number; tag: string; count: number; approved: boolean }
interface TagGroup { id: number; canonical: string; tags: TagItem[]; total: number; reason: string; selected: boolean }

let _nextId = 10000
const newId = () => _nextId++

export default function TagCleanupTab() {
  const [groups,   setGroups]   = useState<TagGroup[]>([])
  const [orphans,  setOrphans]  = useState<TagItem[]>([])
  const [loading,  setLoading]  = useState(false)
  const [saving,   setSaving]   = useState(false)
  const [toast,    setToast]    = useState('')
  const [dragTag,  setDragTag]  = useState<number | null>(null)
  const [dragFrom, setDragFrom] = useState<number | null>(null)   // null = orphan zone
  const [overZone, setOverZone] = useState<number | 'orphan' | null>(null)

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(''), 2800) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const raw = await api('/api/ai/vocabulary/ai-similar?limit=50')
      setGroups((raw as any[]).map((g: any, i: number) => ({
        id:        i + 1,
        canonical: g.canonical_tag,
        tags:      (g.tags || []).map((t: any) => ({ id: t.id, tag: t.tag, count: t.count || 0, approved: t.approved })),
        total:     g.total_count || 0,
        reason:    g.reason || '',
        selected:  true,
      })))
      setOrphans([])
    } catch (e) {
      showToast('Fejl ved hentning af AI-forslag')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // ── Drag helpers ───────────────────────────────────────────────────────────

  const findTag = (tagId: number, fromGroup: number | null): TagItem | undefined => {
    if (fromGroup === null) return orphans.find(t => t.id === tagId)
    return groups.find(g => g.id === fromGroup)?.tags.find(t => t.id === tagId)
  }

  const removeFromSource = (tagId: number, fromGroup: number | null) => {
    if (fromGroup === null) {
      setOrphans(o => o.filter(t => t.id !== tagId))
    } else {
      setGroups(gs => gs.map(g =>
        g.id === fromGroup
          ? { ...g, tags: g.tags.filter(t => t.id !== tagId), total: g.tags.filter(t => t.id !== tagId).length }
          : g
      ))
    }
  }

  const handleDrop = (targetGroupId: number | null) => {
    if (dragTag === null || targetGroupId === dragFrom) { setOverZone(null); return }
    const tag = findTag(dragTag, dragFrom)
    if (!tag) { setOverZone(null); return }
    removeFromSource(dragTag, dragFrom)
    if (targetGroupId === null) {
      setOrphans(o => [...o, tag])
    } else {
      setGroups(gs => gs.map(g =>
        g.id === targetGroupId
          ? { ...g, tags: [...g.tags, tag], total: g.tags.length + 1 }
          : g
      ))
    }
    setDragTag(null); setDragFrom(null); setOverZone(null)
  }

  const removeTagToOrphans = (tagId: number, fromGroup: number | null) => {
    const tag = findTag(tagId, fromGroup)
    if (!tag) return
    removeFromSource(tagId, fromGroup)
    setOrphans(o => [...o, tag])
  }

  const disbandGroup = (groupId: number) => {
    const g = groups.find(g => g.id === groupId)
    if (!g) return
    setOrphans(o => [...o, ...g.tags])
    setGroups(gs => gs.filter(g => g.id !== groupId))
  }

  const toggleSelect = (groupId: number) =>
    setGroups(gs => gs.map(g => g.id === groupId ? { ...g, selected: !g.selected } : g))

  const toggleAll = () => {
    const all = groups.every(g => g.selected)
    setGroups(gs => gs.map(g => ({ ...g, selected: !all })))
  }

  const addGroup = () => {
    const name = window.prompt('Navn på ny gruppe:', 'ny_gruppe')
    if (!name) return
    setGroups(gs => [...gs, { id: newId(), canonical: name.toLowerCase().replace(/\s+/g, '_'), tags: [], total: 0, reason: 'Manuel', selected: true }])
  }

  const updateCanonical = (groupId: number, value: string) =>
    setGroups(gs => gs.map(g => g.id === groupId ? { ...g, canonical: value.toLowerCase().trim().replace(/\s+/g, '_') } : g))

  const save = async () => {
    const selected = groups.filter(g => g.selected && g.tags.length >= 2)
    if (!selected.length) { showToast('Vælg mindst én gruppe med 2+ tags'); return }
    setSaving(true)
    try {
      for (const g of selected) {
        await api('/api/ai/vocabulary/merge', {
          method: 'POST',
          body: JSON.stringify({ source_tag_ids: g.tags.map(t => t.id), canonical_tag: g.canonical }),
        })
      }
      showToast(`✓ ${selected.length} grupper merget (${selected.reduce((s, g) => s + g.tags.length, 0)} tags)`)
      await load()
    } catch {
      showToast('Fejl ved merge — tjek loggen')
    } finally {
      setSaving(false)
    }
  }

  const selectedCount = groups.filter(g => g.selected).length
  const totalTags = groups.reduce((s, g) => s + g.tags.length, 0) + orphans.length

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Brain className="w-4 h-4 text-violet-400" />
            Tag oprydning
          </h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Gemini AI finder lignende tags — træk og slip for at omgruppere
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{groups.length} grupper · {totalTags} tags</span>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Kør AI igen
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-16 space-y-3">
          <Brain className="w-8 h-8 text-violet-400 mx-auto animate-pulse" />
          <p className="text-slate-400 text-sm">Gemini analyserer dine tags...</p>
        </div>
      ) : (
        <>
          {/* Select all */}
          {groups.length > 0 && (
            <div className="flex items-center gap-3">
              <button onClick={toggleAll} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors">
                {groups.every(g => g.selected)
                  ? <><CheckSquare className="w-3.5 h-3.5 text-violet-400" /> Fravælg alle</>
                  : <><Square className="w-3.5 h-3.5" /> Vælg alle</>
                }
              </button>
              {selectedCount > 0 && (
                <span className="text-xs text-violet-400">{selectedCount} valgt til merge</span>
              )}
            </div>
          )}

          {/* Groups grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {groups.map(g => (
              <div
                key={g.id}
                onDragOver={e => { e.preventDefault(); setOverZone(g.id) }}
                onDragLeave={() => setOverZone(null)}
                onDrop={() => handleDrop(g.id)}
                className={`rounded-xl border p-3 transition-all ${
                  overZone === g.id
                    ? 'border-violet-500/60 bg-violet-950/30'
                    : g.selected
                    ? 'border-violet-800/40 bg-gray-900'
                    : 'border-white/8 bg-gray-900'
                }`}
              >
                {/* Canonical name */}
                <div className="flex items-center gap-2 mb-2">
                  <input
                    defaultValue={g.canonical}
                    onBlur={e => updateCanonical(g.id, e.target.value)}
                    className="flex-1 min-w-0 bg-transparent text-xs font-medium text-white border-b border-transparent focus:border-violet-500/50 outline-none pb-0.5 transition-colors font-mono"
                  />
                  <span className="text-xs text-slate-500 shrink-0">×{g.total}</span>
                  <button
                    onClick={() => toggleSelect(g.id)}
                    className={`shrink-0 transition-colors ${g.selected ? 'text-violet-400' : 'text-slate-600 hover:text-slate-400'}`}
                    aria-label={g.selected ? 'Fravælg' : 'Vælg'}
                  >
                    {g.selected ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
                  </button>
                </div>

                {/* Reason */}
                {g.reason && (
                  <p className="text-xs text-slate-500 mb-2 truncate" title={g.reason}>{g.reason}</p>
                )}

                {/* Tags */}
                <div className="flex flex-wrap gap-1 min-h-6">
                  {g.tags.map(t => (
                    <span
                      key={t.id}
                      draggable
                      onDragStart={() => { setDragTag(t.id); setDragFrom(g.id) }}
                      onDragEnd={() => { setDragTag(null); setDragFrom(null); setOverZone(null) }}
                      className={`inline-flex items-center gap-1 font-mono text-xs px-1.5 py-0.5 rounded-full border cursor-grab active:cursor-grabbing transition-opacity ${
                        dragTag === t.id ? 'opacity-30' : 'opacity-100'
                      } ${
                        t.approved
                          ? 'bg-violet-950/50 border-violet-700/40 text-violet-300'
                          : 'bg-gray-800 border-white/8 text-slate-400'
                      }`}
                    >
                      #{t.tag}
                      <button
                        onClick={() => removeTagToOrphans(t.id, g.id)}
                        className="text-slate-600 hover:text-red-400 transition-colors leading-none"
                        aria-label="Fjern fra gruppe"
                      >×</button>
                    </span>
                  ))}
                  {g.tags.length === 0 && (
                    <span className="text-xs text-slate-600 italic">Træk tags hertil</span>
                  )}
                </div>

                {/* Footer */}
                <div className="flex justify-end mt-2 pt-2 border-t border-white/5">
                  <button
                    onClick={() => disbandGroup(g.id)}
                    className="text-slate-600 hover:text-red-400 transition-colors"
                    title="Opløs gruppe"
                    aria-label="Opløs gruppe"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Orphan zone */}
          <div
            onDragOver={e => { e.preventDefault(); setOverZone('orphan') }}
            onDragLeave={() => setOverZone(null)}
            onDrop={() => handleDrop(null)}
            className={`rounded-xl border-2 border-dashed p-3 transition-all ${
              overZone === 'orphan'
                ? 'border-violet-500/60 bg-violet-950/20'
                : 'border-white/10 bg-gray-900/40'
            }`}
          >
            <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
              <Archive className="w-3.5 h-3.5" />
              Fjernet fra grupper — træk hertil for at fjerne fra merge
            </div>
            <div className="flex flex-wrap gap-1.5">
              {orphans.map(t => (
                <span
                  key={t.id}
                  draggable
                  onDragStart={() => { setDragTag(t.id); setDragFrom(null) }}
                  onDragEnd={() => { setDragTag(null); setDragFrom(null); setOverZone(null) }}
                  className="inline-flex items-center gap-1 font-mono text-xs px-1.5 py-0.5 rounded-full bg-gray-800 border border-white/8 text-slate-500 cursor-grab"
                >
                  #{t.tag}
                </span>
              ))}
              {orphans.length === 0 && <span className="text-xs text-slate-600 italic">Tom</span>}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={addGroup}
              className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white px-3 py-1.5 rounded-lg border border-white/8 hover:bg-white/5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Ny gruppe
            </button>
            <div className="flex-1" />
            <button
              onClick={save}
              disabled={saving || selectedCount === 0}
              className="flex items-center gap-2 text-sm font-medium text-white bg-violet-600 hover:bg-violet-500 px-4 py-2 rounded-xl transition-colors disabled:opacity-40"
            >
              <Check className="w-4 h-4" />
              {saving ? 'Merger...' : `Gem og merge ${selectedCount > 0 ? `(${selectedCount})` : ''}`}
            </button>
          </div>
        </>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-gray-900 border border-white/10 rounded-xl px-4 py-3 text-sm text-white shadow-xl z-50">
          {toast}
        </div>
      )}
    </div>
  )
}
