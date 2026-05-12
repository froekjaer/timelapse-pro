// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — ImportPage.tsx
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useState, useRef } from 'react'
import { Upload, FolderOpen, Package, CheckCircle, AlertTriangle, Clock, ChevronRight, RefreshCw, Server } from 'lucide-react'
import { getApiUrl } from '../api/client'

interface Customer { id: number; name: string }
interface Site { id: string; name: string; customer_id: string }
interface ImportJob {
  job_id: string; status: string; total: number; processed: number
  errors: number; pct: number; log: string[]; started_at: string
  finished_at: string | null; device_id: string
  customer: string; site: string; camera_name: string
}

function api(path: string) {
  return fetch(`${getApiUrl()}${path}`, { credentials: 'include' })
}

export function ImportPage() {
  const [customers, setCustomers]     = useState<Customer[]>([])
  const [sites, setSites]             = useState<Site[]>([])
  const [customerId, setCustomerId]   = useState('')
  const [siteId, setSiteId]           = useState('')
  const [cameraName, setCameraName]   = useState('')
  const [mode, setMode]               = useState<'local' | 'zip'>('local')
  const [localPath, setLocalPath]     = useState('')
  const [zipFile, setZipFile]         = useState<File | null>(null)
  const [sftpUser, setSftpUser]       = useState('sftp_nvj17c')
  const [submitting, setSubmitting]   = useState(false)
  const [activeJob, setActiveJob]     = useState<ImportJob | null>(null)
  const [jobs, setJobs]               = useState<ImportJob[]>([])
  const [error, setError]             = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  // Hent kunder
  useEffect(() => {
    api('/api/admin/customers').then(r => r.json()).then(d => setCustomers(d || []))
    loadJobs()
  }, [])

  // Hent alle sites ved mount
  useEffect(() => {
    api('/api/admin/sites').then(r => r.json()).then(d => setSites(Array.isArray(d) ? d : []))
  }, [])
  useEffect(() => { setSiteId('') }, [customerId])

  async function loadJobs() {
    try {
      const r = await api('/api/import/jobs')
      const data = await r.json()
      setJobs(data)
    } catch { /* ignore */ }
  }

  // Poll aktivt job
  useEffect(() => {
    if (!activeJob || activeJob.status === 'done') return
    const t = setInterval(async () => {
      const r = await api(`/api/import/status/${activeJob.job_id}`)
      const data: ImportJob = await r.json()
      setActiveJob(data)
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
      if (data.status === 'done') {
        clearInterval(t)
        loadJobs()
      }
    }, 2000)
    return () => clearInterval(t)
  }, [activeJob])

  async function startImport() {
    setError('')
    if (!customerId || !siteId || !cameraName) {
      setError('Udfyld kunde, site og kameranavnet')
      return
    }
    if (mode === 'local' && !localPath) {
      setError('Angiv sti til billedmappe')
      return
    }
    if (mode === 'zip' && !zipFile) {
      setError('Vælg en ZIP-fil')
      return
    }

    setSubmitting(true)
    const form = new FormData()
    form.append('customer_id', customerId)
    form.append('site_id', siteId)
    form.append('camera_name', cameraName)
    form.append('sftp_user', sftpUser)
    if (mode === 'local') form.append('local_path', localPath)
    if (mode === 'zip' && zipFile) form.append('zip_file', zipFile)

    try {
      const r = await fetch(`${getApiUrl()}/api/import/start`, {
        method: 'POST',
        body: form,
        credentials: 'include',
      })
      if (!r.ok) {
        const err = await r.json()
        setError(err.detail || 'Import fejlede')
        return
      }
      const data = await r.json()
      // Start polling
      const r2 = await api(`/api/import/status/${data.job_id}`)
      setActiveJob(await r2.json())
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const filteredSites = sites.filter(s => s.customer_id === customerId)

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Upload className="w-6 h-6 text-sky-600" />
          Import historiske billeder
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Importér billeder fra andre timelapse-systemer — omdøbes, kvalitetstjekkes og registreres.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Venstre: Import-form */}
        <div className="space-y-5">

          {/* Kunde */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">1. Vælg destination</h2>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Kunde</label>
                <select
                  value={customerId}
                  onChange={e => setCustomerId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Vælg kunde…</option>
                  {customers.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 block mb-1">Site</label>
                <select
                  value={siteId}
                  onChange={e => setSiteId(e.target.value)}
                  disabled={!customerId}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                >
                  <option value="">Vælg site…</option>
                  {filteredSites.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 block mb-1">Kameranavn (nyt virtuelt kamera)</label>
                <input
                  type="text"
                  value={cameraName}
                  onChange={e => setCameraName(e.target.value)}
                  placeholder="f.eks. Kamera 2 — Historisk"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                />
                {cameraName && customerId && siteId && (
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    Device ID: TL-IMPORT-{customers.find(c => String(c.id) === customerId)?.name?.replace(/[^A-Za-z0-9]/g, '_').slice(0, 15)}-{sites.find(s => String(s.id) === siteId)?.name?.replace(/[^A-Za-z0-9]/g, '_').slice(0, 15)}-{cameraName.replace(/[^A-Za-z0-9]/g, '_').slice(0, 15)}
                  </p>
                )}
              </div>

              <div>
                <label className="text-xs text-gray-500 block mb-1">SFTP-bruger (destination)</label>
                <input
                  type="text"
                  value={sftpUser}
                  onChange={e => setSftpUser(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
            </div>
          </div>

          {/* Kilde */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">2. Vælg kilde</h2>

            {/* Mode toggle */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setMode('local')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  mode === 'local'
                    ? 'bg-sky-600 text-white border-sky-600'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'
                }`}
              >
                <FolderOpen className="w-4 h-4" />
                Lokal mappe
              </button>
              <button
                onClick={() => setMode('zip')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  mode === 'zip'
                    ? 'bg-sky-600 text-white border-sky-600'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'
                }`}
              >
                <Package className="w-4 h-4" />
                ZIP-fil (upload)
              </button>
            </div>

            {mode === 'local' ? (
              <div>
                <label className="text-xs text-gray-500 block mb-1">
                  Sti på Mac Mini
                </label>
                <input
                  type="text"
                  value={localPath}
                  onChange={e => setLocalPath(e.target.value)}
                  placeholder="/Users/peter/Downloads/archive"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Søger rekursivt i mappen og undermapper efter JPG-filer.
                </p>
              </div>
            ) : (
              <div>
                <label className="text-xs text-gray-500 block mb-1">ZIP-fil med billeder</label>
                <input
                  type="file"
                  accept=".zip"
                  onChange={e => setZipFile(e.target.files?.[0] || null)}
                  className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-sky-50 file:text-sky-700 hover:file:bg-sky-100"
                />
                {zipFile && (
                  <p className="text-xs text-gray-400 mt-1">
                    {(zipFile.size / 1024 / 1024).toFixed(0)} MB
                  </p>
                )}
              </div>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <button
            onClick={startImport}
            disabled={submitting || (activeJob?.status === 'running')}
            className="w-full bg-sky-600 text-white py-3 rounded-xl font-medium hover:bg-sky-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            <Upload className="w-5 h-5" />
            {submitting ? 'Starter…' : 'Start import'}
          </button>
        </div>

        {/* Højre: Progress + job-historik */}
        <div className="space-y-5">

          {/* Aktivt job */}
          {activeJob && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className={`px-5 py-3 border-b ${
                activeJob.status === 'done'
                  ? 'bg-green-50 border-green-100'
                  : 'bg-sky-50 border-sky-100'
              }`}>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                    {activeJob.status === 'done'
                      ? <CheckCircle className="w-4 h-4 text-green-500" />
                      : <RefreshCw className="w-4 h-4 text-sky-500 animate-spin" />
                    }
                    {activeJob.status === 'done' ? 'Import færdig' : 'Importerer…'}
                  </h3>
                  <span className="text-xs text-gray-500 font-mono">{activeJob.job_id}</span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {activeJob.customer} › {activeJob.site} › {activeJob.camera_name}
                </div>
              </div>

              <div className="px-5 py-4">
                {/* Progress bar */}
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        activeJob.status === 'done' ? 'bg-green-500' : 'bg-sky-500'
                      }`}
                      style={{ width: `${activeJob.pct}%` }}
                    />
                  </div>
                  <span className="text-sm font-bold text-gray-900 w-12 text-right">
                    {activeJob.pct}%
                  </span>
                </div>

                <div className="flex justify-between text-xs text-gray-500 mb-4">
                  <span>{activeJob.processed} / {activeJob.total} billeder</span>
                  {activeJob.errors > 0 && (
                    <span className="text-amber-600">{activeJob.errors} fejl</span>
                  )}
                </div>

                {/* Log */}
                <div
                  ref={logRef}
                  className="bg-gray-900 rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs"
                >
                  {activeJob.log?.map((line, i) => (
                    <div key={i} className={`leading-relaxed ${
                      line.startsWith('⚠️') ? 'text-amber-400' :
                      line.startsWith('🎉') ? 'text-green-400' :
                      line.startsWith('🚀') ? 'text-sky-400' :
                      'text-gray-300'
                    }`}>
                      {line}
                    </div>
                  ))}
                </div>

                {activeJob.status === 'done' && (
                  <div className="mt-3 flex items-center gap-2">
                    <Server className="w-4 h-4 text-gray-400" />
                    <span className="text-xs text-gray-500 font-mono">{activeJob.device_id}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Job-historik */}
          {jobs.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-700 flex items-center justify-between">
                  Tidligere imports
                  <button onClick={loadJobs} className="text-gray-400 hover:text-gray-600">
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </h3>
              </div>
              <div className="divide-y divide-gray-50">
                {jobs.slice(0, 8).map(job => (
                  <div
                    key={job.job_id}
                    className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-gray-50"
                    onClick={() => setActiveJob(job as any)}
                  >
                    {job.status === 'done'
                      ? <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                      : <Clock className="w-4 h-4 text-sky-500 flex-shrink-0" />
                    }
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-900 truncate">
                        {job.customer} › {job.site}
                      </div>
                      <div className="text-xs text-gray-400">
                        {job.camera_name} · {job.processed}/{job.total} billeder
                        {job.errors > 0 && <span className="text-amber-500 ml-1">· {job.errors} fejl</span>}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info-boks */}
          <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 text-xs text-sky-700 space-y-1.5">
            <p className="font-semibold">Hvad sker der ved import?</p>
            <p>✓ Filnavne omdøbes til standard format</p>
            <p>✓ EXIF læses fra originale billeder</p>
            <p>✓ Sidecar JSON skrives (identisk med live captures)</p>
            <p>✓ XMP metadata skrives via exiftool</p>
            <p>✓ Kvalitetstjek: blur + eksponering</p>
            <p>✓ Registreres i databasen</p>
            <p>✓ Originale filer røres ikke</p>
          </div>
        </div>
      </div>
    </div>
  )
}
