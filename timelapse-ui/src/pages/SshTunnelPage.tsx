// ═══════════════════════════════════════════════════════════════
// SshTunnelPage.tsx
// Version: 1.0.0  |  08. maj 2026
// ═══════════════════════════════════════════════════════════════
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, Terminal, RefreshCw, ChevronDown, ChevronRight,
  Wifi, WifiOff, Clock, Activity, Copy, CheckCircle, KeyRound, ShieldAlert, ShieldCheck
} from 'lucide-react'
import { getApiUrl } from '../api/client'
import { SshTerminalModal } from '../components/SshTerminalModal'
import { InfoTooltip } from '../components/InfoTooltip'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    headers: {
      'Content-Type': 'application/json',

    }, ...opts
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface ActiveTunnel {
  device_id:    string
  remote_port:  number
  local_port:   number | null
  connected_at: string
  ssh_user?: string
  ssh_identity_path?: string
  ssh_command?: string
  device_ip?: string | null
  servicetekniker_command?: string | null
  terminal?: {
    allowed: boolean
    reason?: string
    fingerprint?: string
    trusted_state?: string
  }
}

interface TunnelLogEntry {
  event:        string
  remote_port:  number | null
  duration_s:   number | null
  initiated_by: string
  event_at:     string | null
}

function fmt(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

function dur(s: number | null): string {
  if (s === null) return '—'
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}t ${Math.floor((s % 3600) / 60)}m`
}

function eventBadge(event: string) {
  const map: Record<string, string> = {
    connected:    'bg-green-50 text-green-700 border-green-200',
    disconnected: 'bg-gray-50 text-gray-500 border-gray-200',
    failed:       'bg-red-50 text-red-600 border-red-200',
    timeout:      'bg-amber-50 text-amber-600 border-amber-200',
  }
  return map[event] ?? 'bg-gray-50 text-gray-500 border-gray-200'
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy}
      className="ml-2 p-1 rounded hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600">
      {copied
        ? <CheckCircle className="w-3.5 h-3.5 text-green-500" />
        : <Copy className="w-3.5 h-3.5" />}
    </button>
  )
}

function TunnelLog({ deviceId }: { deviceId: string }) {
  const [open, setOpen]       = useState(false)
  const [log, setLog]         = useState<TunnelLogEntry[]>([])
  const [loading, setLoading] = useState(false)

  async function load() {
    if (log.length > 0) return
    setLoading(true)
    try {
      const data = await api(`/api/ssh-tunnel/log/${deviceId}`)
      setLog(Array.isArray(data) ? data : data.entries ?? [])
    } catch { /* ignorér */ }
    finally { setLoading(false) }
  }

  function toggle() {
    if (!open) load()
    setOpen(o => !o)
  }

  return (
    <div className="mt-3">
      <button onClick={toggle}
        className="flex items-center gap-1.5 text-xs text-sky-600 hover:text-sky-800 transition-colors">
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        Audit log
      </button>
      {open && (
        <div className="mt-2 border border-gray-100 rounded-lg overflow-hidden">
          {loading && <p className="text-xs text-gray-400 px-3 py-2">Indlæser…</p>}
          {!loading && log.length === 0 && <p className="text-xs text-gray-400 px-3 py-2">Ingen logposter</p>}
          {!loading && log.length > 0 && (
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-400 border-b border-gray-100">
                  <th className="px-3 py-2 text-left font-medium">Hændelse</th>
                  <th className="px-3 py-2 text-left font-medium">Port</th>
                  <th className="px-3 py-2 text-left font-medium">Varighed</th>
                  <th className="px-3 py-2 text-left font-medium">Initieret af</th>
                  <th className="px-3 py-2 text-left font-medium">Tidspunkt</th>
                </tr>
              </thead>
              <tbody>
                {log.map((e, i) => (
                  <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <span className={`inline-flex px-1.5 py-0.5 rounded border text-[11px] font-medium ${eventBadge(e.event)}`}>
                        {e.event}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-gray-600">{e.remote_port ?? '—'}</td>
                    <td className="px-3 py-2 text-gray-500">{dur(e.duration_s)}</td>
                    <td className="px-3 py-2 text-gray-500">{e.initiated_by}</td>
                    <td className="px-3 py-2 text-gray-400">{fmt(e.event_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

interface CommissioningKeyStatus {
  disabled: boolean
  disabled_at: string | null
  disabled_by: string | null
  servicetekniker_verified_at: string | null
  can_disable: boolean
}

function CommissioningKeyStatus({ deviceId }: { deviceId: string }) {
  const [status, setStatus]     = useState<CommissioningKeyStatus | null>(null)
  const [busy, setBusy]         = useState(false)
  const [confirming, setConfirming] = useState(false)

  const load = useCallback(async () => {
    try {
      setStatus(await api(`/api/admin/devices/${deviceId}/commissioning-key`))
    } catch { /* ignorér */ }
  }, [deviceId])

  useEffect(() => { load() }, [load])

  async function disable() {
    setBusy(true)
    try {
      setStatus(await api(`/api/admin/devices/${deviceId}/commissioning-key/disable`, { method: 'POST' }))
      setConfirming(false)
    } catch { /* fejl vises via can_disable/disabled forbliver uændret */ }
    finally { setBusy(false) }
  }

  if (!status || status.disabled) {
    return status?.disabled ? (
      <p className="mt-3 flex items-center gap-1.5 text-xs text-green-600">
        <ShieldCheck className="w-3.5 h-3.5" />
        Commissioning-nøgle deaktiveret{status.disabled_by ? ` af ${status.disabled_by}` : ''}{status.disabled_at ? ` · ${fmt(status.disabled_at)}` : ''}
      </p>
    ) : null
  }

  return (
    <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
      <p className="flex items-center gap-1.5 text-xs font-medium text-amber-700">
        <ShieldAlert className="w-3.5 h-3.5" />
        Commissioning-nøgle er stadig aktiveret på denne enhed
      </p>
      <p className="mt-1 text-xs text-amber-600">
        {status.servicetekniker_verified_at
          ? `Personlig servicetekniker-adgang bekræftet ${fmt(status.servicetekniker_verified_at)} — kan nu deaktiveres.`
          : 'Log ind som servicetekniker med din egen nøgle mindst én gang, før commissioning-nøglen kan deaktiveres.'}
      </p>
      {!confirming ? (
        <button
          onClick={() => setConfirming(true)}
          disabled={!status.can_disable}
          className="mt-2 px-3 py-1.5 rounded-md text-xs font-medium border border-amber-300 text-amber-700 hover:bg-amber-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Deaktivér commissioning-nøgle
        </button>
      ) : (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-amber-700">Sikker? Dette fjerner den delte nøgle fra enheden permanent.</span>
          <button onClick={disable} disabled={busy}
            className="px-2.5 py-1 rounded-md text-xs font-medium bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50">
            {busy ? 'Deaktiverer…' : 'Ja, deaktivér'}
          </button>
          <button onClick={() => setConfirming(false)} disabled={busy}
            className="px-2.5 py-1 rounded-md text-xs font-medium border border-gray-200 text-gray-500 hover:bg-gray-50">
            Annullér
          </button>
        </div>
      )}
    </div>
  )
}

export function SshTunnelPage() {
  const [tunnels, setTunnels]       = useState<ActiveTunnel[]>([])
  const [loading, setLoading]       = useState(true)
  const [lastRefresh, setLast]      = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [terminalDevice, setTerminalDevice] = useState<string | null>(null)

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true)
    try {
      const data = await api('/api/ssh-tunnel/active')
      setTunnels(Array.isArray(data) ? data : [])
      setLast(new Date())
    } catch { /* headend unreachable */ }
    finally { setLoading(false); setRefreshing(false) }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(() => load(), 30_000)
    return () => clearInterval(t)
  }, [load])

  const sshCmd = (t: ActiveTunnel) =>
    t.ssh_command ?? `ssh -p ${t.remote_port} -i ${t.ssh_identity_path ?? '~/.ssh/timelapse_headend_ed25519'} ${t.ssh_user ?? 'orangepi'}@localhost`

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <Terminal className="w-5 h-5 text-gray-400" />
            SSH Tunnels
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">Aktive reverse SSH tunnels — opdateres hvert 30s</p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-300 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {lastRefresh.toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button onClick={() => load(true)} disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Opdatér
          </button>
        </div>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <Activity className="w-6 h-6 text-gray-300 mx-auto mb-2 animate-pulse" />
          <p className="text-sm text-gray-400">Henter tunnel status…</p>
        </div>
      ) : tunnels.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-10 text-center">
          <WifiOff className="w-8 h-8 text-gray-200 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-500">Ingen aktive SSH tunnels</p>
          <p className="text-xs text-gray-300 mt-1">Tunnels vises her når edge-enheder opretter forbindelse</p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-gray-400 mb-2">
            {tunnels.length} aktiv{tunnels.length !== 1 ? 'e' : ''} tunnel{tunnels.length !== 1 ? 's' : ''}
          </p>
          {tunnels.map(t => (
            <div key={t.device_id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-400 shadow shadow-green-200 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-gray-800 font-mono">{t.device_id}</p>
                    <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                      <Wifi className="w-3 h-3" />
                      Forbundet {fmt(t.connected_at)}
                    </p>
                  </div>
                </div>
                <span className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full font-medium">Aktiv</span>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-gray-50 rounded-lg px-3 py-2.5">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-0.5 flex items-center gap-1">Remote port
                    <InfoTooltip label="Remote port" text={'Porten på headend-serveren som Edge-enhedens reverse tunnel lytter på.\nSSH til enheden sker via denne port: ssh -p <port> …\nHver enhed har sin egen unikke port.'} />
                  </p>
                  <p className="text-sm font-mono font-semibold text-gray-800">{t.remote_port}</p>
                </div>
                <div className="bg-gray-50 rounded-lg px-3 py-2.5">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-0.5">Identity</p>
                  <p className="text-sm font-mono font-semibold text-gray-800 truncate" title={t.ssh_identity_path ?? '~/.ssh/timelapse_headend_ed25519'}>
                    {t.ssh_identity_path ?? '~/.ssh/timelapse_headend_ed25519'}
                  </p>
                </div>
              </div>
              <div className="bg-gray-900 rounded-lg px-3 py-2.5 flex items-center justify-between gap-3">
                <code className="text-xs text-green-400 font-mono break-all">{sshCmd(t)}</code>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <CopyBtn text={sshCmd(t)} />
                  <button
                    onClick={() => setTerminalDevice(t.device_id)}
                    disabled={!t.terminal?.allowed}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-green-700/50 text-green-300 hover:bg-green-900/30 disabled:border-gray-700 disabled:text-gray-500 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
                    title={t.terminal?.allowed ? 'Åbn terminal i browser' : (t.terminal?.reason ?? 'SSH host identity er ikke trusted')}
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    Åbn terminal
                  </button>
                </div>
              </div>
              {!t.terminal?.allowed && (
                <p className="mt-2 text-xs text-amber-600">
                  Browserterminal er deaktiveret: {t.terminal?.reason ?? 'SSH host identity er ikke trusted/verified'}
                </p>
              )}
              {t.servicetekniker_command && (
                <div className="mt-3">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">
                    Login som servicetekniker (direkte, egen nøgle — kræver samme netværk som enheden)
                  </p>
                  <div className="bg-gray-900 rounded-lg px-3 py-2.5 flex items-center justify-between gap-3">
                    <code className="text-xs text-sky-300 font-mono break-all">{t.servicetekniker_command}</code>
                    <CopyBtn text={t.servicetekniker_command} />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    Erstat <code className="font-mono">&lt;din-private-nøgle&gt;</code> med stien til din egen nøglefil — den kan headend ikke kende, da din private nøgle aldrig sendes til serveren.
                  </p>
                </div>
              )}
              <CommissioningKeyStatus deviceId={t.device_id} />
              <TunnelLog deviceId={t.device_id} />
            </div>
          ))}
        </div>
      )}
      {terminalDevice && (
        <SshTerminalModal deviceId={terminalDevice} onClose={() => setTerminalDevice(null)} />
      )}
    </div>
  )
}
