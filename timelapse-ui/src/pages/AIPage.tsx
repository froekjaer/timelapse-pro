// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — AIPage.tsx
// ───────────────────────────────────────────────────────────────────────────
// AI-styring: strategi pr. kunde, tag-review, eskalering, daglig korrektion
// ═══════════════════════════════════════════════════════════════════════════

import TagCleanupTab from './TagCleanupTab'
import React, { useEffect, useState, useCallback } from 'react'
import {
  Brain, Tags, AlertTriangle, CalendarCheck,
  BarChart3, CheckCircle, XCircle,
  Cloud, Cpu, Zap, RefreshCw, Send, Eye, ThumbsUp, ThumbsDown,
  TrendingUp, Layers, SlidersHorizontal, Info, ShieldCheck, Database, Server,
  Save, FileText
} from 'lucide-react'
import { getApiUrl } from '../api/client'
import { CaptureThumbnailCard } from '../components/CaptureThumbnailCard'
import type { Capture } from '../types'

const api = (path: string, opts?: RequestInit) =>
  fetch(`${getApiUrl()}${path}`, opts).then(async r => {
    const data = await r.json().catch(() => null)
    if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`)
    return data
  })

// ── Types ─────────────────────────────────────────────────────────────────

type Strategy = 'technical_only' | 'local_only' | 'local_then_cloud' | 'cloud_only'

interface AIConfig {
  id: number
  customer_id: string | null
  site_id: string | null
  customer_name: string | null
  strategy: Strategy
  local_model: string
  cloud_model: string
  escalation_threshold: number
  escalation_new_tags: number
  tag_vocabulary_limit: number
  enabled: boolean
  notes: string | null
  display_name: string
}

interface PendingTag {
  id: number
  tag: string
  count: number
  first_seen: string
  last_seen: string
  canonical_tag?: string | null
  display_name_da?: string | null
  display_name_en?: string | null
  translation_status?: string | null
}

interface EscalationItem {
  analysis_id: number
  capture_id: number
  filename: string
  captured_at: string
  escalation_score: number
  escalation_reasons: string[]
  current_tags: string[]
  quality_flag: string
  change_detected: boolean
}

interface DayCapture {
  capture_id: number
  filename: string
  captured_at: string
  scene_dk: string
  current_tags: string[]
  quality_flag: string
  quality_ok: boolean
  corrected_tags: string[] | null
  is_corrected: boolean
  should_escalate: boolean
  gemini_tags: string[] | null
}

interface AccuracyStat {
  dt: string
  total: number
  no_changes_needed: number
  accuracy_pct: number
}

interface TagStat {
  tag: string
  category: string
  total_count: number
  location_count: number
  approved: boolean
}

function captureFromPath(path: string, overrides: Partial<Capture> = {}): Capture {
  const parts = path.split('/')
  const hasDevicePrefix = parts.length > 1
  return {
    id: overrides.id ?? 0,
    device_id: overrides.device_id ?? (hasDevicePrefix ? parts[0] : ''),
    filename: overrides.filename ?? (hasDevicePrefix ? parts.slice(1).join('/') : path),
    captured_at: overrides.captured_at ?? null,
    quality_flag: overrides.quality_flag ?? null,
    quality_passed: overrides.quality_passed ?? null,
    blur_score: overrides.blur_score ?? null,
    filesize_mb: overrides.filesize_mb ?? null,
    uploaded: overrides.uploaded ?? true,
    ai_result: overrides.ai_result ?? null,
    ai_analyzed_at: overrides.ai_analyzed_at ?? null,
    ai_tags: overrides.ai_tags ?? null,
  }
}

// ── Strategy helpers ──────────────────────────────────────────────────────

const STRATEGY_META: Record<Strategy, { label: string; color: string; icon: React.ReactElement; desc: string }> = {
  technical_only:   { label: 'Kun OpenCV',        color: 'text-slate-400 bg-slate-800',  icon: <Cpu className="w-3.5 h-3.5" />,   desc: 'Ingen AI — kun blur/brightness' },
  local_only:       { label: 'Lokal Ollama',       color: 'text-emerald-400 bg-emerald-950', icon: <Cpu className="w-3.5 h-3.5" />,   desc: 'Kun lokal model, ingen cloud' },
  local_then_cloud: { label: 'Lokal → Cloud',      color: 'text-amber-400 bg-amber-950',  icon: <Zap className="w-3.5 h-3.5" />,   desc: 'Lokal model, Gemini ved usikkerhed' },
  cloud_only:       { label: 'Kun Gemini',         color: 'text-sky-400 bg-sky-950',      icon: <Cloud className="w-3.5 h-3.5" />, desc: 'Alt til Gemini Flash' },
}

function StrategyBadge({ strategy }: { strategy: Strategy }) {
  const m = STRATEGY_META[strategy]
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${m.color}`}>
      {m.icon}{m.label}
    </span>
  )
}

// ── Tabs ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'runtime',    label: 'Modeller & prompts', icon: Brain },
  { id: 'strategy',   label: 'Strategi',       icon: SlidersHorizontal },
  { id: 'tags',       label: 'Tag Review',      icon: Tags },
  { id: 'cleanup',    label: 'Tag Oprydning',   icon: Layers },
  { id: 'aiops',      label: 'AI Ops',           icon: ShieldCheck },
  { id: 'escalation', label: 'Eskalering',      icon: AlertTriangle },
  { id: 'review',     label: 'Daglig Review',   icon: CalendarCheck },
  { id: 'stats',      label: 'Statistik',       icon: BarChart3 },
]

// ═════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═════════════════════════════════════════════════════════════════════════

export default function AIPage() {
  const [tab, setTab] = useState('runtime')

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <div className="border-b border-white/8 bg-gray-900/60 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-3">
          <Brain className="w-5 h-5 text-violet-400" />
          <h1 className="font-semibold text-sm tracking-tight">AI Styring</h1>
          <div className="ml-6 flex items-center gap-1">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all ${
                  tab === t.id
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <t.icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {tab === 'runtime'    && <AIRuntimeTab />}
        {tab === 'strategy'   && <StrategyTab />}
        {tab === 'tags'       && <TagReviewTab />}
        {tab === 'cleanup'    && <TagCleanupTab />}
        {tab === 'aiops'      && <AIOpsTab />}
        {tab === 'escalation' && <EscalationTab />}
        {tab === 'review'     && <DailyReviewTab />}
        {tab === 'stats'      && <StatsTab />}
      </div>
    </div>
  )
}

interface RuntimeField {
  key: string
  label: string
  type: 'text' | 'model' | 'int' | 'float'
  value: string
  default: string
  min?: number
  max?: number
  source: string
}

interface PromptVersion {
  id: number
  version: number
  status: string
  notes?: string | null
  created_by: string
  created_at: string
}

interface AIPrompt {
  id: number | null
  purpose: string
  label: string
  version: number
  status: string
  template: string
  allowed_variables: string[]
  source: string
  history: PromptVersion[]
}

function AIRuntimeTab() {
  const [fields, setFields] = useState<RuntimeField[]>([])
  const [models, setModels] = useState<string[]>([])
  const [prompts, setPrompts] = useState<AIPrompt[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    setBusy(true)
    setMessage(null)
    try {
      const [runtime, promptData] = await Promise.all([
        api('/api/settings/ai-runtime'),
        api('/api/settings/ai-prompts'),
      ])
      setFields(runtime.fields || [])
      setModels(runtime.installed_models || [])
      setPrompts(promptData || [])
      setDrafts(Object.fromEntries((promptData || []).map((p: AIPrompt) => [p.purpose, p.template])))
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Kunne ikke hente AI-konfiguration')
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const saveRuntime = async () => {
    setBusy(true)
    try {
      await api('/api/settings/ai-runtime', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values: Object.fromEntries(fields.map(f => [f.key, f.value])) }),
      })
      setMessage('AI runtime-konfiguration er gemt. Nye analyser bruger værdierne.')
      await load()
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Konfigurationen kunne ikke gemmes')
    } finally { setBusy(false) }
  }

  const saveDraft = async (prompt: AIPrompt) => {
    setBusy(true)
    try {
      await api(`/api/settings/ai-prompts/${prompt.purpose}/draft`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: drafts[prompt.purpose], notes: notes[prompt.purpose] || null }),
      })
      setMessage(`Ny kladde til ${prompt.label} er gemt. Aktiv version er uændret.`)
      await load()
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Promptkladden kunne ikke gemmes')
    } finally { setBusy(false) }
  }

  const activate = async (id: number) => {
    setBusy(true)
    try {
      await api(`/api/settings/ai-prompts/${id}/activate`, { method: 'POST' })
      setMessage('Promptversionen er aktiveret og bruges ved næste analyse.')
      await load()
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Prompten kunne ikke aktiveres')
    } finally { setBusy(false) }
  }

  return <div className="space-y-6">
    <div className="border border-violet-800/40 bg-violet-950/30 rounded-lg p-4 flex gap-3">
      <Info className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
      <div className="text-sm text-slate-300">
        <p>Dette er den autoritative konfiguration for lokal billedanalyse og AI Ops.</p>
        <p className="text-xs text-slate-500 mt-1">Promptændringer gemmes først som kladde og påvirker ikke drift, før en version aktiveres.</p>
      </div>
    </div>
    {message && <div className="border border-white/10 bg-gray-900 rounded-lg px-4 py-3 text-sm text-slate-300">{message}</div>}

    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div><h2 className="font-semibold">Modeller og inferens</h2><p className="text-xs text-slate-500">Installerede modeller: {models.length ? models.join(', ') : 'Ollama svarer ikke'}</p></div>
        <button onClick={saveRuntime} disabled={busy} className="flex items-center gap-2 px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg text-sm"><Save className="w-4 h-4" />Gem alle</button>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
        {fields.map(field => <label key={field.key} className="bg-gray-900 border border-white/8 rounded-lg p-3 block">
          <span className="text-xs text-slate-400 block mb-1.5">{field.label}</span>
          <input list={field.type === 'model' ? 'ollama-models' : undefined}
            type={field.type === 'int' || field.type === 'float' ? 'number' : 'text'}
            min={field.min} max={field.max} step={field.type === 'float' ? '0.01' : undefined}
            value={field.value} onChange={e => setFields(all => all.map(f => f.key === field.key ? { ...f, value: e.target.value } : f))}
            className="w-full bg-gray-800 border border-white/10 rounded-md px-3 py-2 text-sm text-white" />
          <span className="text-[11px] text-slate-600 mt-1 block font-mono">{field.key} · default {field.default}</span>
        </label>)}
      </div>
      <datalist id="ollama-models">{models.map(model => <option key={model} value={model} />)}</datalist>
    </section>

    <section className="space-y-3">
      <div><h2 className="font-semibold">Promptversioner</h2><p className="text-xs text-slate-500">Variabler er tilladelseslistet. Ugyldige eller manglende variable afvises.</p></div>
      {prompts.map(prompt => {
        const newestDraft = prompt.history.find(version => version.status === 'draft')
        return <div key={prompt.purpose} className="bg-gray-900 border border-white/8 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-3">
            <FileText className="w-4 h-4 text-violet-400" />
            <div><h3 className="text-sm font-medium">{prompt.label}</h3><p className="text-xs text-slate-500">{prompt.purpose} · aktiv v{prompt.version} · {prompt.source}</p></div>
            {newestDraft && <button onClick={() => activate(newestDraft.id)} disabled={busy} className="ml-auto px-3 py-1.5 border border-emerald-700 text-emerald-300 hover:bg-emerald-950 rounded-md text-xs">Aktivér kladde v{newestDraft.version}</button>}
          </div>
          <div className="text-xs text-slate-500">Tilladte variable: {prompt.allowed_variables.map(v => `{{${v}}}`).join(', ')}</div>
          <textarea value={drafts[prompt.purpose] || ''} onChange={e => setDrafts(d => ({ ...d, [prompt.purpose]: e.target.value }))}
            rows={9} className="w-full bg-gray-950 border border-white/10 rounded-md p-3 text-xs text-slate-200 font-mono resize-y" />
          <div className="flex gap-2">
            <input value={notes[prompt.purpose] || ''} onChange={e => setNotes(n => ({ ...n, [prompt.purpose]: e.target.value }))} placeholder="Ændringsnote (anbefalet)" className="flex-1 bg-gray-800 border border-white/10 rounded-md px-3 py-2 text-sm" />
            <button onClick={() => saveDraft(prompt)} disabled={busy} className="px-3 py-2 border border-white/10 hover:bg-white/5 rounded-md text-sm">Gem som ny kladde</button>
          </div>
        </div>
      })}
    </section>
  </div>
}

// ═════════════════════════════════════════════════════════════════════════
// AI OPS TAB
// ═════════════════════════════════════════════════════════════════════════

interface AIOpsRecommendation {
  title: string
  severity: string
  domain: string[]
  rationale: string
  proposed_action: string
  requires_acceptance: boolean
}

interface AIOpsAnalysis {
  mode: string
  summary: string
  risk_level: string
  recommendations: AIOpsRecommendation[]
  next_checks: string[]
}

interface AIOpsSnapshot {
  generated_at: string
  guardrails: Record<string, boolean>
  cmdb: { device_count_by_status: Record<string, number>; inventory_rows: number }
  siem: { last_24h_by_severity: Record<string, number>; latest_critical: unknown[] }
  updates: { by_status: Record<string, number>; artifact_count: number; change_ticket_count: number }
  keys: Record<string, number>
  resilience: { counts?: Record<string, number>; devices?: number; change_tickets?: number }
  sast: { files_scanned: number; finding_count: number; findings: { category: string; file: string; line: number; snippet: string }[] }
}

function severityClass(level: string) {
  const map: Record<string, string> = {
    critical: 'bg-red-600 text-white border-red-500',
    high: 'bg-red-950 text-red-200 border-red-800',
    medium: 'bg-amber-950 text-amber-200 border-amber-800',
    low: 'bg-emerald-950 text-emerald-200 border-emerald-800',
  }
  return map[level] ?? 'bg-slate-800 text-slate-300 border-white/10'
}

function MiniMetric({ label, value, icon: Icon }: { label: string; value: number | string; icon: React.ElementType }) {
  return (
    <div className="bg-gray-900 border border-white/8 rounded-xl p-4">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Icon className="w-4 h-4" />
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    </div>
  )
}

function AIOpsTab() {
  const [snapshot, setSnapshot] = useState<AIOpsSnapshot | null>(null)
  const [analysis, setAnalysis] = useState<AIOpsAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSnapshot = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      setSnapshot(await api('/api/ai/ops/snapshot'))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke hente AI Ops snapshot')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadSnapshot() }, [loadSnapshot])

  const runAnalysis = async () => {
    setError(null)
    setLoading(true)
    try {
      const data = await api('/api/ai/ops/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      setSnapshot(data.snapshot)
      setAnalysis(data.analysis)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'AI Ops analyse fejlede')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="bg-violet-950/40 border border-violet-800/30 rounded-xl p-4 flex gap-3">
        <ShieldCheck className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
        <div className="text-sm text-slate-300 space-y-1">
          <p>AI Ops bruger Ollama som read-only co-pilot på CMDB, SIEM, updates, key management, resilience og SAST-signaler.</p>
          <p className="text-slate-400 text-xs">Modellen må ikke ændre database, køre kommandoer eller remediate uden menneskelig accept. Forslag skal videre som change tickets eller manuelle beslutninger.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-800/40 text-red-200 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={runAnalysis} disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-sm font-medium">
          <Brain className="w-4 h-4" />
          Kør Ollama AI Ops analyse
        </button>
        <button onClick={loadSnapshot} disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-900 border border-white/10 hover:bg-white/5 disabled:opacity-50 text-sm text-slate-300">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Opdater snapshot
        </button>
        {snapshot && <span className="text-xs text-slate-500">Snapshot: {new Date(snapshot.generated_at).toLocaleString('da-DK')}</span>}
      </div>

      {snapshot && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniMetric label="CMDB enheder" value={Object.values(snapshot.cmdb.device_count_by_status || {}).reduce((a, b) => a + b, 0)} icon={Server} />
          <MiniMetric label="SIEM 24h events" value={Object.values(snapshot.siem.last_24h_by_severity || {}).reduce((a, b) => a + b, 0)} icon={AlertTriangle} />
          <MiniMetric label="Updates" value={Object.values(snapshot.updates.by_status || {}).reduce((a, b) => a + b, 0)} icon={RefreshCw} />
          <MiniMetric label="SAST findings" value={snapshot.sast.finding_count} icon={Database} />
        </div>
      )}

      {analysis && (
        <div className="bg-gray-900 border border-white/8 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-white/8 flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-white">AI Ops vurdering</h2>
                <span className={`text-[11px] px-2 py-0.5 rounded border ${severityClass(analysis.risk_level)}`}>{analysis.risk_level}</span>
                <span className="text-[11px] px-2 py-0.5 rounded border border-white/10 text-slate-400">{analysis.mode}</span>
              </div>
              <p className="text-sm text-slate-300 mt-2">{analysis.summary}</p>
            </div>
          </div>

          <div className="divide-y divide-white/6">
            {analysis.recommendations.map((rec, idx) => (
              <div key={`${rec.title}-${idx}`} className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-semibold text-white">{rec.title}</h3>
                      <span className={`text-[11px] px-2 py-0.5 rounded border ${severityClass(rec.severity)}`}>{rec.severity}</span>
                      {rec.requires_acceptance && (
                        <span className="text-[11px] px-2 py-0.5 rounded border border-amber-700 bg-amber-950 text-amber-200">kræver accept</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-400 mt-2">{rec.rationale}</p>
                    <p className="text-sm text-slate-200 mt-2">{rec.proposed_action}</p>
                    <div className="mt-3 flex gap-1 flex-wrap">
                      {rec.domain.map(d => (
                        <span key={d} className="text-[11px] px-1.5 py-0.5 rounded border border-white/10 bg-black/20 text-slate-400">{d}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {snapshot?.sast.findings.length ? (
        <div className="bg-gray-900 border border-white/8 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-white/8">
            <h2 className="text-sm font-semibold text-white">SAST review-signaler</h2>
            <p className="text-xs text-slate-500 mt-1">Read-only heuristik. Fund skal vurderes før change ticket.</p>
          </div>
          <div className="divide-y divide-white/6 max-h-96 overflow-auto">
            {snapshot.sast.findings.slice(0, 25).map((f, idx) => (
              <div key={`${f.file}-${f.line}-${idx}`} className="px-5 py-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-violet-300">{f.category}</span>
                  <span className="text-slate-500 font-mono">{f.file}:{f.line}</span>
                </div>
                <code className="block mt-1 text-slate-400 whitespace-pre-wrap">{f.snippet}</code>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// STRATEGI TAB
// ═════════════════════════════════════════════════════════════════════════

function StrategyTab() {
  const [configs, setConfigs] = useState<AIConfig[]>([])
  const [localModels, setLocalModels] = useState<string[]>([])
  const [editing, setEditing] = useState<AIConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving,  setSaving]  = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api('/api/settings/config').then(d => { setConfigs(Array.isArray(d) ? d : []); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    api('/api/settings/ai-runtime')
      .then(d => setLocalModels(Array.isArray(d.installed_models) ? d.installed_models : []))
      .catch(() => setLocalModels([]))
  }, [load])

  const save = async () => {
    if (!editing) return
    setSaving(true)
    try {
      await api('/api/settings/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editing),
      })
      setEditing(null)
      load()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Forklaring */}
      <div className="bg-violet-950/40 border border-violet-800/30 rounded-xl p-4 flex gap-3">
        <Info className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
        <div className="text-sm text-slate-300 space-y-1">
          <p>Strategi bestemmer hvilken AI der bruges pr. kunde. Fallback-hierarki: <strong>Site → Kunde → Global</strong></p>
          <p className="text-slate-400 text-xs">Ændringer træder i kraft ved næste analyse. Eksisterende analyser påvirkes ikke.</p>
        </div>
      </div>

      {/* Strategi-forklaring */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {(Object.entries(STRATEGY_META) as [Strategy, typeof STRATEGY_META[Strategy]][]).map(([key, m]) => (
          <div key={key} className="bg-gray-900 border border-white/8 rounded-xl p-3 space-y-1">
            <div className="flex items-center gap-2">
              <StrategyBadge strategy={key} />
            </div>
            <p className="text-xs text-slate-400">{m.desc}</p>
          </div>
        ))}
      </div>

      {/* Tabel */}
      {loading ? (
        <div className="text-center py-12 text-slate-500">Henter konfiguration...</div>
      ) : (
        <div className="bg-gray-900 border border-white/8 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/8 text-xs text-slate-500 uppercase tracking-wider">
                <th className="px-4 py-3 text-left">Scope</th>
                <th className="px-4 py-3 text-left">Strategi</th>
                <th className="px-4 py-3 text-left">Lokal model</th>
                <th className="px-4 py-3 text-left">Threshold</th>
                <th className="px-4 py-3 text-left">Vocab limit</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {configs.map(cfg => (
                <tr key={cfg.id} className="hover:bg-white/3 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">{cfg.display_name}</div>
                    {cfg.notes && <div className="text-xs text-slate-500 mt-0.5">{cfg.notes}</div>}
                  </td>
                  <td className="px-4 py-3"><StrategyBadge strategy={cfg.strategy} /></td>
                  <td className="px-4 py-3 text-slate-400 font-mono text-xs">{cfg.local_model}</td>
                  <td className="px-4 py-3 text-slate-400">{cfg.escalation_threshold}</td>
                  <td className="px-4 py-3 text-slate-400">{cfg.tag_vocabulary_limit}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${cfg.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>
                      {cfg.enabled ? '● Aktiv' : '○ Deaktiveret'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setEditing({ ...cfg })}
                      className="text-xs text-violet-400 hover:text-violet-300 px-2 py-1 rounded-lg hover:bg-violet-900/30 transition-colors"
                    >
                      Rediger
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-white/10 rounded-2xl w-full max-w-lg p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-white">{editing.display_name}</h2>
              <button onClick={() => setEditing(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            {/* Strategi */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Vælg AI strategi: Technical_only (kun OpenCV kvalitetskontrol, ingen tags), Local_only (kun Ollama, offline), Local_then_cloud (Ollama først, Gemini ved usikkerhed), Cloud_only (kun Gemini Flash, bedste kvalitet). Cloud kræver API nøgle.">Strategi</label>
              <div className="grid grid-cols-2 gap-2">
                {(Object.keys(STRATEGY_META) as Strategy[]).map(s => (
                  <button
                    key={s}
                    onClick={() => setEditing({ ...editing, strategy: s })}
                    className={`flex items-start gap-2 p-3 rounded-xl border text-left transition-all ${
                      editing.strategy === s
                        ? 'border-violet-500 bg-violet-950/50'
                        : 'border-white/8 bg-gray-800 hover:border-white/20'
                    }`}
                    title={STRATEGY_META[s].desc}
                  >
                    <div className="mt-0.5"><StrategyBadge strategy={s} /></div>
                    <p className="text-xs text-slate-400 mt-0.5">{STRATEGY_META[s].desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Lokal model */}
            {(editing.strategy === 'local_only' || editing.strategy === 'local_then_cloud') && (
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Lokal vision model til tag analyse. qwen2.5vl:7b (anbefalet - balance mellem hastighed og kvalitet), llama3.2-vision:11b (tung men meget præcis), llava-phi3:latest (hurtig men mindre præcis). Modellen skal være pulled på Ollama server.">Lokal model</label>
                <select
                  value={editing.local_model}
                  onChange={e => setEditing({ ...editing, local_model: e.target.value })}
                  className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
                  title="Lokal vision model til tag analyse. qwen2.5vl:7b (anbefalet - balance mellem hastighed og kvalitet), llama3.2-vision:11b (tung men meget præcis), llava-phi3:latest (hurtig men mindre præcis). Modellen skal være pulled på Ollama server."
                >
                  {!localModels.includes(editing.local_model) && <option value={editing.local_model}>{editing.local_model} (konfigureret, ikke fundet)</option>}
                  {localModels.map(model => <option key={model} value={model}>{model}</option>)}
                </select>
              </div>
            )}

            {/* Thresholds */}
            {editing.strategy === 'local_then_cloud' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Confidence tærskel for eskalering til Gemini. Hvis lokal model confidence er under denne værdi (fx 0.70), sendes billedet til Gemini for bedre analyse. Højere værdi = mere cloud usage. Lavere værdi = flere locale resultater. Typisk 0.60-0.80.">
                    Eskalér hvis confidence &lt;
                  </label>
                  <input
                    type="number" min="0.5" max="1" step="0.05"
                    value={editing.escalation_threshold}
                    onChange={e => setEditing({ ...editing, escalation_threshold: parseFloat(e.target.value) })}
                    className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
                    title="Confidence tærskel (0.5-1.0). Hvis lokal model er usikker, eskaler til Gemini. Højere = mere cloud usage. Typisk 0.60-0.80."
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Maksimalt antal nye/ukendte tags før eskalering til Gemini. Hvis lokal model finder mere end N tags der ikke er i vocab, sendes til Gemini for at udvide vokabulariet. Højere værdi = mere lokal autonomy. Typisk 3-10 nye tags.">
                    Eskalér hvis &gt; N nye tags
                  </label>
                  <input
                    type="number" min="1" max="20"
                    value={editing.escalation_new_tags}
                    onChange={e => setEditing({ ...editing, escalation_new_tags: parseInt(e.target.value) })}
                    className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
                    title="Maksimalt antal nye tags før eskalering (1-20). Højt tal = mere lokal autonomy. Typisk 3-10."
                  />
                </div>
              </div>
            )}

            {/* Vocab limit */}
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-medium uppercase tracking-wider" title="Maksimalt antal tags i AI prompt for at begrænse token forbrug og øge hastighed. Færre tags = hurtigere analyse. 372 = fulde vokabular (alle tags). Typisk 100-300 for balance mellem hastighed og dækning.">
                Max tags i prompt (performance)
              </label>
              <input
                type="number" min="20" max="372" step="10"
                value={editing.tag_vocabulary_limit}
                onChange={e => setEditing({ ...editing, tag_vocabulary_limit: parseInt(e.target.value) })}
                className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
                title="Max tags i prompt (20-372). Færre = hurtigere analyse. 372 = alle tags. Typisk 100-300."
              />
              <p className="text-xs text-slate-500">Færre = hurtigere. 372 = alle tags</p>
            </div>

            {/* Enabled */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300" title="Aktiver AI tag analyse for denne kunde. Når deaktiveret, springes AI analyse over og captures markeres manuelt eller uden tags. Kan bruges til at pause AI eller kunder der ikke ønsker automatisk tagning.">AI aktiveret for denne kunde</span>
              <button
                onClick={() => setEditing({ ...editing, enabled: !editing.enabled })}
                className={`w-11 h-6 rounded-full transition-colors ${editing.enabled ? 'bg-violet-600' : 'bg-gray-700'}`}
                title="Klik for at toggle AI aktivering for denne kunde"
              >
                <div className={`w-4 h-4 rounded-full bg-white mx-auto transition-transform ${editing.enabled ? 'translate-x-2.5' : '-translate-x-2.5'}`} />
              </button>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setEditing(null)}
                className="flex-1 px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Annuller
              </button>
              <button
                onClick={save}
                disabled={saving}
                className="flex-1 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-sm font-medium transition-colors disabled:opacity-50"
              >
                {saving ? 'Gemmer...' : 'Gem'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// TAG REVIEW TAB
// ═════════════════════════════════════════════════════════════════════════

function TagReviewTab() {
  const [tags,    setTags]    = useState<PendingTag[]>([])
  const [loading, setLoading] = useState(true)
  const [busy,    setBusy]    = useState<Set<number>>(new Set())
  const [daEdits, setDaEdits] = useState<Record<number, string>>({})

  const load = () => {
    setLoading(true)
    api('/api/ai/vocabulary/pending').then(d => { setTags(Array.isArray(d) ? d : []); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const approve = async (id: number, category?: string) => {
    setBusy(b => new Set(b).add(id))
    // Hvis admin har rettet det danske forslag, gem det FØRST, så godkendelsen
    // sker med det korrigerede navn, ikke AI's oprindelige gæt.
    if (daEdits[id] !== undefined) {
      await saveTranslation(id, daEdits[id])
    }
    await api(`/api/ai/vocabulary/${id}/approve${category ? `?category=${category}` : ''}`, { method: 'POST' })
    setTags(t => t.filter(x => x.id !== id))
    setBusy(b => { const s = new Set(b); s.delete(id); return s })
  }

  const reject = async (id: number) => {
    setBusy(b => new Set(b).add(id))
    await api(`/api/ai/vocabulary/${id}/reject`, { method: 'POST' })
    setTags(t => t.filter(x => x.id !== id))
    setBusy(b => { const s = new Set(b); s.delete(id); return s })
  }

  const saveTranslation = async (id: number, displayNameDa: string) => {
    await api(`/api/ai/vocabulary/${id}/translation`, {
      method: 'PUT',
      body: JSON.stringify({ display_name_da: displayNameDa }),
    })
    setTags(t => t.map(x => x.id === id ? { ...x, display_name_da: displayNameDa, translation_status: 'approved' } : x))
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-white">Model-opfundne tags</h2>
          <p className="text-sm text-slate-400 mt-0.5">Tags AI-modellen har fundet selv — godkend eller afvis</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Opdater
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500">Henter tags...</div>
      ) : tags.length === 0 ? (
        <div className="text-center py-16">
          <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
          <p className="text-slate-400">Ingen tags afventer godkendelse</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-white/8 rounded-xl overflow-hidden">
          <div className="px-4 py-2 border-b border-white/5 text-xs text-slate-500 flex gap-4">
            <span>{tags.length} tags afventer</span>
            <button
              onClick={() => tags.forEach(t => approve(t.id))}
              className="text-emerald-400 hover:text-emerald-300"
            >
              Godkend alle →
            </button>
          </div>
          <div className="divide-y divide-white/5">
            {tags.map(tag => {
              const statusBadge: Record<string, { label: string; cls: string }> = {
                pending:      { label: 'Mangler dansk', cls: 'bg-amber-900/40 text-amber-400' },
                ai_suggested: { label: 'AI-forslag', cls: 'bg-blue-900/40 text-blue-400' },
                approved:     { label: 'Bekræftet', cls: 'bg-emerald-900/40 text-emerald-400' },
              }
              const badge = statusBadge[tag.translation_status ?? 'pending'] ?? statusBadge.pending
              const daValue = daEdits[tag.id] ?? tag.display_name_da ?? ''
              return (
              <div key={tag.id} className="flex items-center gap-3 px-4 py-3 hover:bg-white/3 transition-colors">
                <code className="text-sm text-violet-300 font-mono bg-violet-950/50 px-2 py-0.5 rounded-lg">
                  #{tag.tag}
                </code>
                <span className="text-slate-600 text-xs">→</span>
                <div className="flex-1 flex items-center gap-2">
                  <input
                    type="text"
                    value={daValue}
                    onChange={e => setDaEdits(d => ({ ...d, [tag.id]: e.target.value }))}
                    onBlur={() => { if (daEdits[tag.id] !== undefined && daEdits[tag.id] !== tag.display_name_da) saveTranslation(tag.id, daEdits[tag.id]) }}
                    placeholder="Dansk oversættelse..."
                    className="bg-gray-800 border border-white/10 rounded-lg px-2 py-1 text-sm text-slate-200 w-44 focus:outline-none focus:border-violet-500"
                  />
                  <span className={`text-xs px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.label}</span>
                </div>
                <span className="text-xs text-slate-500">set {tag.count}×</span>
                <span className="text-xs text-slate-600">
                  {new Date(tag.first_seen).toLocaleDateString('da-DK')}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => approve(tag.id)}
                    disabled={busy.has(tag.id)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-900/50 text-emerald-400 hover:bg-emerald-800/50 text-xs transition-colors disabled:opacity-40"
                  >
                    <ThumbsUp className="w-3 h-3" /> Godkend
                  </button>
                  <button
                    onClick={() => reject(tag.id)}
                    disabled={busy.has(tag.id)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-900/30 text-red-400 hover:bg-red-800/30 text-xs transition-colors disabled:opacity-40"
                  >
                    <ThumbsDown className="w-3 h-3" /> Afvis
                  </button>
                </div>
              </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// ESKALERING TAB
// ═════════════════════════════════════════════════════════════════════════

function EscalationTab() {
  const [items,    setItems]    = useState<EscalationItem[]>([])
  const [loading,  setLoading]  = useState(true)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [sending,  setSending]  = useState(false)
  const [stats,    setStats]    = useState<any>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api('/api/review/escalation/pending?limit=100'),
      api('/api/review/escalation/stats?days=7'),
    ]).then(([q, s]) => {
      setItems(Array.isArray(q.items) ? q.items : [])
      setStats(s)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const toggle = (id: number) =>
    setSelected(s => { const n = new Set(s); if (n.has(id)) { n.delete(id) } else { n.add(id) }; return n })

  const approveSelected = async () => {
    if (selected.size === 0) return
    setSending(true)
    await api('/api/review/escalation/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_ids: [...selected], admin_id: 'admin' }),
    })
    setSending(false)
    setSelected(new Set())
    load()
  }

  const rejectSelected = async () => {
    if (selected.size === 0) return
    await api('/api/review/escalation/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_ids: [...selected], admin_id: 'admin' }),
    })
    setSelected(new Set())
    load()
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Afventer',   value: stats.pending,   color: 'text-amber-400' },
            { label: 'Godkendt',   value: stats.approved,  color: 'text-sky-400' },
            { label: 'Afvist',     value: stats.rejected,  color: 'text-slate-400' },
            { label: 'Fuldført',   value: stats.completed, color: 'text-emerald-400' },
          ].map(s => (
            <div key={s.label} className="bg-gray-900 border border-white/8 rounded-xl p-4 text-center">
              <div className={`text-2xl font-bold ${s.color}`}>{s.value ?? 0}</div>
              <div className="text-xs text-slate-500 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 bg-violet-950/40 border border-violet-800/30 rounded-xl px-4 py-3">
          <span className="text-sm text-violet-300">{selected.size} billeder valgt</span>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={rejectSelected}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white border border-white/10 hover:bg-white/5 transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" /> Afvis
            </button>
            <button
              onClick={approveSelected}
              disabled={sending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-violet-600 hover:bg-violet-500 transition-colors disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {sending ? 'Sender til Gemini...' : 'Send til Gemini'}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-500">Henter eskalerings-kø...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
          <p className="text-slate-400">Ingen billeder afventer Gemini-analyse</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-white/8 rounded-xl overflow-hidden">
          <div className="px-4 py-2 border-b border-white/5 flex items-center gap-3">
            <button
              onClick={() => setSelected(selected.size === items.length ? new Set() : new Set(items.map(i => i.analysis_id)))}
              className="text-xs text-slate-400 hover:text-white"
            >
              {selected.size === items.length ? 'Fravælg alle' : 'Vælg alle'}
            </button>
            <span className="text-xs text-slate-600">{items.length} billeder</span>
          </div>
          <div className="divide-y divide-white/5">
            {items.map(item => (
              <div
                key={item.analysis_id}
                className={`flex items-center gap-4 px-4 py-3 cursor-pointer transition-colors hover:bg-white/3 ${selected.has(item.analysis_id) ? 'bg-violet-950/20' : ''}`}
                onClick={() => toggle(item.analysis_id)}
              >
                <input
                  type="checkbox"
                  checked={selected.has(item.analysis_id)}
                  readOnly
                  className="w-4 h-4 rounded accent-violet-500"
                />
                <div className="w-32 shrink-0">
                  <CaptureThumbnailCard
                    capture={captureFromPath(item.filename, {
                      id: item.capture_id,
                      captured_at: item.captured_at,
                      quality_flag: item.quality_flag,
                      ai_tags: item.current_tags,
                    })}
                    compact
                    onClick={() => {}}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">{item.filename.split('/').pop()}</div>
                  <div className="flex gap-2 mt-1 flex-wrap">
                    {item.escalation_reasons.map(r => (
                      <span key={r} className="text-xs bg-amber-950/50 text-amber-400 px-1.5 py-0.5 rounded">{r}</span>
                    ))}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xs font-mono text-amber-400">{(item.escalation_score * 100).toFixed(0)}%</div>
                  <div className="text-xs text-slate-500">usikkerhed</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// DAGLIG REVIEW TAB
// ═════════════════════════════════════════════════════════════════════════

function DailyReviewTab() {
  const today = new Date().toISOString().split('T')[0]
  const [date,     setDate]     = useState(today)
  const [captures, setCaptures] = useState<DayCapture[]>([])
  const [loading,  setLoading]  = useState(false)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTags,  setEditTags]  = useState('')
  const [saving,   setSaving]   = useState(false)

  const load = () => {
    setLoading(true)
    api(`/api/review/day/${date}?limit=200`).then(d => {
      setCaptures(Array.isArray(d.captures) ? d.captures : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  const startSession = async () => {
    const d = await api('/api/review/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_date: date, admin_id: 'admin' }),
    })
    setSessionId(d.session_id)
    load()
  }

  const saveCorrection = async (cap: DayCapture) => {
    let sid = sessionId
    if (!sid) {
      const d = await api('/api/review/session/start', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({session_date: date, admin_id: 'admin'})
      })
      sid = d.session_id
      setSessionId(sid)
    }
    if (!sid) return
    setSaving(true)
    const tags = editTags.split(',').map(t => t.trim().toLowerCase()).filter(Boolean)
    await api('/api/review/correction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        capture_id: cap.capture_id,
        session_id: sid,
        admin_id: 'admin',
        corrected_tags: tags,
        corrected_quality_flag: cap.quality_flag,
        corrected_quality_ok: cap.quality_ok,
      }),
    })
    setSaving(false)
    setEditingId(null)
    load()
  }

  const completeSession = async () => {
    if (!sessionId) return
    const result = await api(`/api/review/session/${sessionId}/complete`, { method: 'POST' })
    alert(`Session afsluttet! ${result.examples_generated} nye prompt-eksempler genereret.`)
    setSessionId(null)
  }

  return (
    <div className="space-y-4">
      {/* Datovælger + session */}
      <div className="flex items-center gap-4">
        <input
          type="date" value={date}
          onChange={e => setDate(e.target.value)}
          className="bg-gray-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
        />
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-sm transition-colors">
          <Eye className="w-3.5 h-3.5" /> Hent billeder
        </button>
        {!sessionId ? (
          <button onClick={startSession} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-sm font-medium transition-colors">
            Start korrektions-session
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <span className="text-sm text-emerald-400">Session #{sessionId} aktiv</span>
            <button onClick={completeSession} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-sm font-medium transition-colors">
              <CheckCircle className="w-3.5 h-3.5" /> Afslut session
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500">Henter billeder...</div>
      ) : captures.length === 0 ? (
        <div className="text-center py-12 text-slate-500">Ingen analyserede billeder for {date}</div>
      ) : (
        <div className="space-y-2">
          <div className="text-xs text-slate-500 px-1">{captures.length} billeder · {captures.filter(c => c.is_corrected).length} korrigerede</div>
          {captures.map(cap => (
            <div
              key={cap.capture_id}
              className={`bg-gray-900 border rounded-xl overflow-hidden transition-all ${
                cap.is_corrected ? 'border-emerald-800/40' : 'border-white/8'
              }`}
            >
              <div className="flex gap-4 p-4">
                <div className="w-32 shrink-0">
                  <CaptureThumbnailCard
                    capture={captureFromPath(cap.filename, {
                      id: cap.capture_id,
                      captured_at: cap.captured_at,
                      quality_flag: cap.quality_flag,
                      ai_tags: cap.current_tags,
                    })}
                    compact
                    onClick={() => {}}
                  />
                </div>
                <div className="flex-1 min-w-0 space-y-2">
                  {/* Scene */}
                  <p className="text-sm text-slate-300">{cap.scene_dk || 'Ingen beskrivelse'}</p>
                  {/* Tags */}
                  <div className="flex flex-wrap gap-1">
                    {(cap.corrected_tags || cap.current_tags || []).slice(0, 20).map(tag => (
                      <span key={tag} className={`text-xs px-1.5 py-0.5 rounded font-mono ${
                        cap.is_corrected ? 'bg-emerald-950/50 text-emerald-300' : 'bg-gray-800 text-slate-400'
                      }`}>#{tag}</span>
                    ))}
                  </div>
                  {/* Meta */}
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span>{new Date(cap.captured_at).toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })}</span>
                    <span>{cap.quality_flag}</span>
                    {cap.should_escalate && <span className="text-amber-400">🔺 eskaleret</span>}
                    {cap.gemini_tags && <span className="text-sky-400">☁️ Gemini</span>}
                    {cap.is_corrected && <span className="text-emerald-400">✓ korrigeret</span>}
                  </div>
                </div>
                {/* Rediger knap */}
                {sessionId && (
                  <button
                    onClick={() => {
                      setEditingId(cap.capture_id)
                      setEditTags((cap.corrected_tags || cap.current_tags || []).join(', '))
                    }}
                    className="shrink-0 text-xs text-violet-400 hover:text-violet-300 px-3 py-1.5 rounded-lg hover:bg-violet-900/30 transition-colors self-start"
                  >
                    Ret
                  </button>
                )}
              </div>

              {/* Edit panel */}
              {editingId === cap.capture_id && (
                <div className="border-t border-white/8 p-4 bg-gray-900/80 space-y-3">
                  <label className="text-xs text-slate-400">Tags (kommasepareret)</label>
                  <textarea
                    value={editTags}
                    onChange={e => setEditTags(e.target.value)}
                    rows={3}
                    className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white font-mono resize-none focus:outline-none focus:border-violet-500/50"
                    placeholder="tag1, tag2, tag3..."
                  />
                  <div className="flex gap-3">
                    <button onClick={() => setEditingId(null)} className="px-4 py-1.5 rounded-lg text-sm text-slate-400 border border-white/10 hover:text-white transition-colors">
                      Annuller
                    </button>
                    <button
                      onClick={() => saveCorrection(cap)}
                      disabled={saving}
                      className="px-4 py-1.5 rounded-lg text-sm font-medium bg-violet-600 hover:bg-violet-500 transition-colors disabled:opacity-50"
                    >
                      {saving ? 'Gemmer...' : 'Gem korrektion'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════
// STATISTIK TAB
// ═════════════════════════════════════════════════════════════════════════

function StatsTab() {
  const [accuracy, setAccuracy] = useState<AccuracyStat[]>([])
  const [tagStats, setTagStats] = useState<TagStat[]>([])
  const [loading,  setLoading]  = useState(true)
  const [tagFilter, setTagFilter] = useState('')

  useEffect(() => {
    Promise.all([
      api('/api/review/stats/accuracy?days=30'),
      api('/api/ai/vocabulary/statistics?limit=200'),
    ]).then(([acc, tags]) => {
      setAccuracy(Array.isArray(acc) ? acc : [])
      setTagStats(Array.isArray(tags) ? tags : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const filteredTags = tagStats.filter(t =>
    !tagFilter || t.tag.includes(tagFilter.toLowerCase())
  )

  if (loading) return <div className="text-center py-12 text-slate-500">Henter statistik...</div>

  return (
    <div className="space-y-6">
      {/* Accuracy trend */}
      {accuracy.length > 0 && (
        <div className="bg-gray-900 border border-white/8 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-violet-400" />
            <h3 className="font-medium text-sm">Model-nøjagtighed over tid</h3>
            <span className="text-xs text-slate-500 ml-auto">% billeder der ikke krævede korrektion</span>
          </div>
          <div className="h-40">
            <div className="flex items-end gap-1 h-full">
              {accuracy.slice(-20).map((a, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-violet-600 rounded-t"
                    style={{ height: `${a.accuracy_pct || 0}%`, minHeight: '2px' }}
                    title={`${a.dt}: ${a.accuracy_pct}%`}
                  />
                  {i % 5 === 0 && (
                    <span className="text-xs text-slate-600 rotate-45 origin-left">
                      {a.dt.slice(5)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tag statistik */}
      <div className="bg-gray-900 border border-white/8 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5 flex items-center gap-3">
          <Layers className="w-4 h-4 text-violet-400" />
          <h3 className="font-medium text-sm">Tag statistik</h3>
          <input
            value={tagFilter}
            onChange={e => setTagFilter(e.target.value)}
            placeholder="Filtrer tags..."
            className="ml-auto bg-gray-800 border border-white/10 rounded-lg px-3 py-1 text-xs text-white w-40"
          />
        </div>
        <div className="divide-y divide-white/5 max-h-96 overflow-y-auto">
          {filteredTags.slice(0, 100).map(t => (
            <div key={t.tag} className="flex items-center gap-3 px-4 py-2 hover:bg-white/3">
              <code className="text-xs text-violet-300 font-mono w-48 truncate">#{t.tag}</code>
              <span className="text-xs text-slate-500 w-24">{t.category}</span>
              <div className="flex-1 bg-gray-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="h-full bg-violet-600 rounded-full"
                  style={{ width: `${Math.min(100, (t.total_count / (tagStats[0]?.total_count || 1)) * 100)}%` }}
                />
              </div>
              <span className="text-xs text-slate-400 w-10 text-right">{t.total_count}×</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
