import { useCallback, useEffect, useState } from 'react'
import {
  Server, Download, KeyRound, AlertTriangle, CheckCircle, Loader2, Archive, Trash2, RefreshCw,
} from 'lucide-react'
import { getApiUrl } from '../api/client'

interface StoredBundle {
  filename: string
  size_bytes: number
  modified_at: string
  environment: string | null
  device_id: string | null
  sha256: string | null
  created_by: string | null
}

interface PrepareResult {
  status: string
  device_id: string
  environment: string
  backend_url: string
  token: string
  expires_at: string
  conf: string
  commands: string[]
  warnings: string[]
}

interface TrustedRelease {
  tag: string
  commit: string
  created_at: string
  subject: string
  signature_status: 'trusted'
}

const inputCls =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
const labelCls = 'block text-sm font-medium text-gray-700 mb-1'

export function HeadendGeneratorTab() {
  const [environment, setEnvironment] = useState<'staging' | 'prod'>('staging')
  const [domain, setDomain] = useState('staging.timelapse-pro.dk')
  const [backendPort, setBackendPort] = useState('8443')
  const [deviceId, setDeviceId] = useState('')
  const [dataDir, setDataDir] = useState('/Users/Shared/TimeLapsePro/data/canonical-images')
  const [repoDir, setRepoDir] = useState('/Users/Shared/TimeLapsePro/releases/staging')
  const [serviceUser, setServiceUser] = useState('_timelapse')
  const [serviceHome, setServiceHome] = useState('/var/lib/timelapse')
  const [tunnelHost, setTunnelHost] = useState('staging.timelapse-pro.dk')
  const [tunnelPort, setTunnelPort] = useState('22222')
  const [tunnelUser, setTunnelUser] = useState('tunnel')
  const [releaseTag, setReleaseTag] = useState('')
  const [expectedCommit, setExpectedCommit] = useState('')
  const [releases, setReleases] = useState<TrustedRelease[]>([])
  const [releaseBusy, setReleaseBusy] = useState(true)
  const [busy, setBusy] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PrepareResult | null>(null)
  const [bundles, setBundles] = useState<StoredBundle[]>([])
  const [storageDir, setStorageDir] = useState('')

  const loadBundles = useCallback(async () => {
    try {
      const res = await fetch(`${getApiUrl()}/api/headend/generator/bundles`, { credentials: 'include' })
      if (!res.ok) return
      const data = await res.json()
      setBundles(data.bundles ?? [])
      setStorageDir(data.storage_dir ?? '')
    } catch { /* listen er ikke kritisk */ }
  }, [])

  const loadReleases = useCallback(async () => {
    setReleaseBusy(true)
    try {
      const res = await fetch(`${getApiUrl()}/api/headend/generator/releases`, { credentials: 'include' })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(data?.detail || `Release-kataloget fejlede (${res.status})`)
      const trusted = (data?.releases ?? []) as TrustedRelease[]
      setReleases(trusted)
      if (trusted.length > 0) {
        const current = trusted.find(release => release.tag === releaseTag) ?? trusted[0]
        setReleaseTag(current.tag)
        setExpectedCommit(current.commit)
      } else {
        setReleaseTag('')
        setExpectedCommit('')
        setError('Ingen lokalt betroede signerede releases er tilgængelige')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setReleaseBusy(false)
    }
  }, [releaseTag])

  useEffect(() => {
    loadBundles()
    loadReleases()
  // Catalog load is intentionally once on mount; the refresh button reloads it explicitly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadBundles])

  const downloadStored = async (filename: string) => {
    try {
      const res = await fetch(`${getApiUrl()}/api/headend/generator/bundles/${encodeURIComponent(filename)}`, {
        credentials: 'include',
      })
      if (!res.ok) throw new Error(`Fejl (${res.status})`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const removeStored = async (filename: string) => {
    if (!window.confirm(`Ryd op i "${filename}"? (Flyttes til .quarantine — pakken indeholder et engangs-token)`)) return
    try {
      const res = await fetch(`${getApiUrl()}/api/headend/generator/bundles/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (!res.ok) throw new Error(`Fejl (${res.status})`)
      await loadBundles()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const payload = () => ({
    environment,
    domain,
    backend_port: Number(backendPort),
    device_id: deviceId || undefined,
    data_dir: dataDir,
    repo_dir: repoDir,
    service_user: serviceUser,
    service_home: serviceHome,
    tunnel_host: tunnelHost,
    tunnel_port: Number(tunnelPort),
    tunnel_user: tunnelUser,
    release_tag: releaseTag,
    expected_commit: expectedCommit,
  })

  const prepare = async () => {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`${getApiUrl()}/api/headend/generator/prepare`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload()),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || `Fejl (${res.status})`)
      setResult(data as PrepareResult)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const downloadBundle = async () => {
    if (!result) return
    setDownloadBusy(true)
    setError(null)
    try {
      const res = await fetch(`${getApiUrl()}/api/headend/generator/bundle`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload(), token: result.token }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Fejl (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `timelapse-headend-installer-${result.environment}.tar.gz`
      a.click()
      URL.revokeObjectURL(url)
      await loadBundles()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDownloadBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Server className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-gray-900">Klargør ny headend (staging/prod)</h2>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Genererer miljøkonfiguration, et engangs-enrollment-token og en installationspakke.
          Installationen køres af dig på den nye Mac fra en GPG-verificeret release — CrushFTP&apos;s
          porte (21/22/80/443) røres aldrig. Fuld manual:{' '}
          <span className="font-mono">INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md</span>
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="headend-environment" className={labelCls}>Miljø</label>
            <select
              id="headend-environment"
              className={inputCls}
              value={environment}
              onChange={e => {
                const env = e.target.value as 'staging' | 'prod'
                setEnvironment(env)
                setDomain(env === 'prod' ? 'backend.timelapse-pro.dk' : 'staging.timelapse-pro.dk')
                setTunnelHost(env === 'prod' ? 'backend.timelapse-pro.dk' : 'staging.timelapse-pro.dk')
                setRepoDir(`/Users/Shared/TimeLapsePro/releases/${env}`)
                setResult(null)
              }}
            >
              <option value="staging">staging</option>
              <option value="prod">prod</option>
            </select>
          </div>
          <div>
            <label htmlFor="headend-domain" className={labelCls}>Backend-domæne</label>
            <input id="headend-domain" className={inputCls} value={domain} onChange={e => setDomain(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-backend-port" className={labelCls}>Port (aldrig 21/22/80/443 — CrushFTP)</label>
            <input id="headend-backend-port" className={inputCls} value={backendPort} onChange={e => setBackendPort(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-device-id" className={labelCls}>Device-ID (tomt = TL-HEADEND-{environment.toUpperCase()}-1)</label>
            <input
              id="headend-device-id"
              className={inputCls}
              placeholder={`TL-HEADEND-${environment.toUpperCase()}-1`}
              value={deviceId}
              onChange={e => setDeviceId(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="headend-data-dir" className={labelCls}>Data-katalog på den nye maskine</label>
            <input id="headend-data-dir" className={inputCls} value={dataDir} onChange={e => setDataDir(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-repo-dir" className={labelCls}>Release-katalog på den nye maskine</label>
            <input id="headend-repo-dir" className={inputCls} value={repoDir} onChange={e => setRepoDir(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-service-user" className={labelCls}>Servicebruger</label>
            <input id="headend-service-user" className={inputCls} value={serviceUser} onChange={e => setServiceUser(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-service-home" className={labelCls}>Servicekontoens hjemmekatalog</label>
            <input id="headend-service-home" className={inputCls} value={serviceHome} onChange={e => setServiceHome(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-tunnel-host" className={labelCls}>Tunnel-host</label>
            <input id="headend-tunnel-host" className={inputCls} value={tunnelHost} onChange={e => setTunnelHost(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-tunnel-port" className={labelCls}>Tunnel-port (dedikeret SSH-ingress)</label>
            <input id="headend-tunnel-port" className={inputCls} value={tunnelPort} onChange={e => setTunnelPort(e.target.value)} />
          </div>
          <div>
            <label htmlFor="headend-tunnel-user" className={labelCls}>Tunnel-bruger</label>
            <input id="headend-tunnel-user" className={inputCls} value={tunnelUser} onChange={e => setTunnelUser(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <label htmlFor="headend-release-tag" className="block text-sm font-medium text-gray-700">Release-tag</label>
              <button
                type="button"
                onClick={loadReleases}
                disabled={releaseBusy}
                className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${releaseBusy ? 'animate-spin' : ''}`} />
                Opdatér liste
              </button>
            </div>
            <select
              id="headend-release-tag"
              className={inputCls}
              value={releaseTag}
              disabled={releaseBusy || releases.length === 0}
              onChange={e => {
                const release = releases.find(item => item.tag === e.target.value)
                setReleaseTag(e.target.value)
                setExpectedCommit(release?.commit ?? '')
                setResult(null)
              }}
            >
              {releases.length === 0 && <option value="">Ingen signerede releases</option>}
              {releases.map(release => (
                <option key={release.tag} value={release.tag}>
                  {release.tag} · {new Date(release.created_at).toLocaleDateString('da-DK')}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label htmlFor="headend-release-commit" className={labelCls}>Forventet commit-SHA (fuld, 40 tegn)</label>
            <select
              id="headend-release-commit"
              className={`${inputCls} font-mono`}
              value={expectedCommit}
              disabled={releaseBusy || releases.length === 0}
              onChange={e => {
                const release = releases.find(item => item.commit === e.target.value)
                setExpectedCommit(e.target.value)
                if (release) setReleaseTag(release.tag)
                setResult(null)
              }}
            >
              {releases.length === 0 && <option value="">Ingen verificerede commits</option>}
              {releases.map(release => (
                <option key={`${release.tag}-${release.commit}`} value={release.commit}>
                  {release.commit} · {release.tag}
                </option>
              ))}
            </select>
            {releaseTag && (
              <p className="mt-1 text-xs text-emerald-700">
                GPG-signaturen er verificeret lokalt · {releases.find(item => item.tag === releaseTag)?.subject}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={prepare}
          disabled={busy || releaseBusy || !releaseTag || !expectedCommit}
          className="mt-4 inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
          Klargør ny headend
        </button>

        {error && (
          <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-emerald-500" />
            <h3 className="text-base font-semibold text-gray-900">
              Klargjort: {result.device_id} → {result.backend_url}
            </h3>
          </div>

          <div>
            <div className="text-sm font-medium text-gray-700 mb-1">
              Engangs-token (udløber {new Date(result.expires_at).toLocaleString('da-DK')} — behandl som hemmelighed)
            </div>
            <code className="block bg-gray-50 border border-gray-200 rounded-lg p-2 text-xs break-all">{result.token}</code>
          </div>

          <div>
            <div className="text-sm font-medium text-gray-700 mb-1">Kørsel på den nye Mac</div>
            <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs overflow-x-auto">
              {result.commands.join('\n')}
            </pre>
          </div>

          {result.warnings.length > 0 && (
            <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
              {result.warnings.map(w => (
                <div key={w} className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={downloadBundle}
            disabled={downloadBusy}
            className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg"
          >
            {downloadBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Download installationspakke (.tar.gz)
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Archive className="w-5 h-5 text-gray-500" />
          <h3 className="text-base font-semibold text-gray-900">Gemte installationspakker (headend-images)</h3>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          {storageDir && <span className="font-mono">{storageDir}</span>} — pakkerne indeholder et
          engangs-enrollment-token: behandl som hemmeligheder og ryd op efter brug.
        </p>
        {bundles.length === 0 ? (
          <p className="text-sm text-gray-500">Ingen gemte pakker endnu.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {bundles.map(b => (
              <div key={b.filename} className="py-2 flex items-center gap-3 text-sm">
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs truncate">{b.filename}</div>
                  <div className="text-xs text-gray-500">
                    {b.environment ?? '?'} · {b.device_id ?? '?'} · {(b.size_bytes / 1024).toFixed(0)} KB ·{' '}
                    {new Date(b.modified_at).toLocaleString('da-DK')}
                    {b.sha256 && <> · sha256 {b.sha256.slice(0, 12)}…</>}
                  </div>
                </div>
                <button
                  onClick={() => downloadStored(b.filename)}
                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium"
                >
                  <Download className="w-4 h-4" /> Hent
                </button>
                <button
                  onClick={() => removeStored(b.filename)}
                  className="inline-flex items-center gap-1 text-red-600 hover:text-red-800 text-xs font-medium"
                >
                  <Trash2 className="w-4 h-4" /> Ryd op
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
