// TimeLapse Pro — NotificationsPage.tsx
// ========================================
// Konfigurér alarm-notifikationer: Email, SMS og Teams.
// Følger samme designsprog som SystemAdminPage.

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Bell, Mail, MessageSquare, Webhook, Save, CheckCircle,
         Send, ChevronDown, ChevronRight, AlertTriangle, Eye, EyeOff } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, { credentials: 'include',
    headers: { 'Content-Type': 'application/json' }, ...opts
  }).then((r: Response) => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

// ── Hjælpekomponenter ─────────────────────────────────────────────────────────

function Section({ title, icon, description, children, badge }: {
  title: string; icon: React.ReactNode; description: string
  children: React.ReactNode; badge?: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-50 transition-colors text-left">
        <span className="text-gray-400">{icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-gray-800">{title}</p>
            {badge}
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{description}</p>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-gray-300" /> : <ChevronRight className="w-4 h-4 text-gray-300" />}
      </button>
      {open && <div className="px-5 pb-5 pt-1 border-t border-gray-100 space-y-4">{children}</div>}
    </div>
  )
}

function Field({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="py-2 border-b border-gray-50 last:border-0">
      <label className="text-xs font-medium text-gray-600 block mb-1">{label}</label>
      {children}
      {description && <p className="text-xs text-gray-300 mt-1">{description}</p>}
    </div>
  )
}

function Txt({ value, onChange, placeholder, mono, type = 'text' }: {
  value: string; onChange: (v: string) => void; placeholder?: string; mono?: boolean; type?: string
}) {
  return (
    <input type={type}
      className={`w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm ${mono ? 'font-mono' : ''}`}
      value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
  )
}

function Toggle({ value, onChange, label }: { value: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div onClick={() => onChange(!value)}
        className={`w-10 h-5 rounded-full transition-colors relative ${value ? 'bg-sky-500' : 'bg-gray-200'}`}>
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${value ? 'left-5' : 'left-0.5'}`} />
      </div>
      <span className="text-sm text-gray-600">{label}</span>
    </label>
  )
}

function EnabledBadge({ enabled }: { enabled: boolean }) {
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-400'}`}>
      {enabled ? 'Aktiv' : 'Inaktiv'}
    </span>
  )
}

function PasswordField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input type={show ? 'text' : 'password'}
        className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono pr-10"
        value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
      <button onClick={() => setShow(s => !s)}
        className="absolute right-2 top-1.5 text-gray-300 hover:text-gray-500">
        {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  )
}

// ── Hoved-komponent ───────────────────────────────────────────────────────────

interface NotifConfig {
  email: {
    enabled: boolean; smtp_host: string; smtp_port: number
    username: string; password: string; from: string; to: string[]
  }
  sms: {
    enabled: boolean; provider: string; api_token: string; sender: string; to: string[]
  }
  teams: { enabled: boolean; webhook_url: string }
  min_severity: string
}

const DEFAULT_CONFIG: NotifConfig = {
  email: { enabled: false, smtp_host: 'smtp.gmail.com', smtp_port: 587, username: '', password: '', from: '', to: [] },
  sms:   { enabled: false, provider: 'gatewayapi', api_token: '', sender: 'TimeLapse', to: [] },
  teams: { enabled: false, webhook_url: '' },
  min_severity: 'warning',
}

export function NotificationsPage() {
  const [cfg, setCfg]         = useState<NotifConfig>(DEFAULT_CONFIG)
  const [saving, setSaving]   = useState(false)
  const [saved, setSaved]     = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, string>>({})

  useEffect(() => {
    api('/api/admin/notifications')
      .then((d: any) => {
        if (d && Object.keys(d).length > 0) {
          setCfg(prev => ({
            ...prev, ...d,
            email: { ...prev.email, ...(d.email || {}) },
            sms:   { ...prev.sms,   ...(d.sms   || {}) },
            teams: { ...prev.teams, ...(d.teams  || {}) },
          }))
        }
      })
      .catch(() => setError('Kunne ikke hente notifikations-konfiguration'))
  }, [])

  function setEmail(k: string, v: any) { setCfg(c => ({ ...c, email: { ...c.email, [k]: v } })) }
  function setSms(k: string, v: any)   { setCfg(c => ({ ...c, sms:   { ...c.sms,   [k]: v } })) }
  function setTeams(k: string, v: any) { setCfg(c => ({ ...c, teams: { ...c.teams, [k]: v } })) }

  async function save() {
    setSaving(true); setError(null)
    try {
      await api('/api/admin/notifications', { method: 'PUT', body: JSON.stringify(cfg) })
      setSaved(true); setTimeout(() => setSaved(false), 2500)
    } catch { setError('Kunne ikke gemme — tjek headend-loggen') }
    finally { setSaving(false) }
  }

  async function test(channel: string) {
    setTesting(channel); setTestResult(r => ({ ...r, [channel]: '' }))
    try {
      const res = await api('/api/admin/notifications/test', { method: 'POST', body: JSON.stringify({ channel }) })
      setTestResult(r => ({ ...r, [channel]: res.status === 'ok' ? '✓ Sendt!' : '✗ Fejlede' }))
    } catch {
      setTestResult(r => ({ ...r, [channel]: '✗ Fejl — tjek log' }))
    }
    setTesting(null)
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/settings" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-sky-500" />
          <h1 className="text-xl font-semibold text-gray-900">Alarm Notifikationer</h1>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto underline">Luk</button>
        </div>
      )}

      {/* Min severity */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Minimum alvorlighedsniveau</h2>
        <p className="text-xs text-gray-400 mb-3">Kun alarmer på dette niveau eller højere sendes som notifikation</p>
        <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={cfg.min_severity} onChange={e => setCfg(c => ({ ...c, min_severity: e.target.value }))}>
          <option value="info">Info — alle alarmer</option>
          <option value="maintenance">Vedligehold og derover</option>
          <option value="warning">Advarsel og derover</option>
          <option value="critical">Kun kritiske alarmer</option>
        </select>
      </div>

      {/* Email */}
      <Section title="Email" icon={<Mail className="w-4 h-4" />}
        description="Gmail eller andet SMTP — nemmest at sætte op"
        badge={<EnabledBadge enabled={cfg.email.enabled} />}>

        <Toggle value={cfg.email.enabled} onChange={v => setEmail('enabled', v)} label="Aktivér email-notifikationer" />

        <Field label="SMTP host" description="Gmail: smtp.gmail.com">
          <Txt value={cfg.email.smtp_host} onChange={v => setEmail('smtp_host', v)} mono placeholder="smtp.gmail.com" />
        </Field>
        <Field label="SMTP port" description="Gmail: 587 (STARTTLS)">
          <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono"
            value={cfg.email.smtp_port} onChange={e => setEmail('smtp_port', parseInt(e.target.value) || 587)} />
        </Field>
        <Field label="Brugernavn (Gmail-adresse)">
          <Txt value={cfg.email.username} onChange={v => setEmail('username', v)} mono placeholder="din@gmail.com" />
        </Field>
        <Field label="App Password" description="16-cifret Gmail App Password — IKKE dit normale password">
          <PasswordField value={cfg.email.password} onChange={v => setEmail('password', v)} placeholder="xxxx xxxx xxxx xxxx" />
        </Field>
        <Field label="Afsender-navn">
          <Txt value={cfg.email.from} onChange={v => setEmail('from', v)} placeholder="TimeLapse Pro <din@gmail.com>" />
        </Field>
        <Field label="Modtagere" description="Kommaseparerede email-adresser">
          <Txt value={(cfg.email.to || []).join(', ')}
            onChange={v => setEmail('to', v.split(',').map(s => s.trim()).filter(Boolean))}
            placeholder="alarm@firma.dk, peter@firma.dk" />
        </Field>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={() => test('email')} disabled={testing === 'email' || !cfg.email.enabled}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 disabled:opacity-40">
            <Send className="w-3.5 h-3.5" />
            {testing === 'email' ? 'Sender…' : 'Send test-email'}
          </button>
          {testResult.email && (
            <span className={`text-sm font-medium ${testResult.email.startsWith('✓') ? 'text-emerald-600' : 'text-red-500'}`}>
              {testResult.email}
            </span>
          )}
        </div>
      </Section>

      {/* SMS */}
      <Section title="SMS via GatewayAPI" icon={<MessageSquare className="w-4 h-4" />}
        description="Dansk SMS-tjeneste — ~0.04 kr/sms — gatewayapi.com"
        badge={<EnabledBadge enabled={cfg.sms.enabled} />}>

        <Toggle value={cfg.sms.enabled} onChange={v => setSms('enabled', v)} label="Aktivér SMS-notifikationer" />

        <Field label="Provider">
          <select className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            value={cfg.sms.provider} onChange={e => setSms('provider', e.target.value)}>
            <option value="gatewayapi">GatewayAPI (anbefalet — dansk)</option>
            <option value="twilio">Twilio</option>
          </select>
        </Field>
        <Field label="API Token" description="Hent på gatewayapi.com → API → Tokens">
          <PasswordField value={cfg.sms.api_token} onChange={v => setSms('api_token', v)} placeholder="••••••••" />
        </Field>
        <Field label="Afsender-navn" description="Max 11 tegn — vises som afsender på SMS">
          <Txt value={cfg.sms.sender} onChange={v => setSms('sender', v.slice(0, 11))} placeholder="TimeLapse" />
        </Field>
        <Field label="Modtagere" description="Kommaseparerede numre med landekode">
          <Txt value={(cfg.sms.to || []).join(', ')}
            onChange={v => setSms('to', v.split(',').map(s => s.trim()).filter(Boolean))}
            placeholder="+4512345678, +4598765432" mono />
        </Field>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={() => test('sms')} disabled={testing === 'sms' || !cfg.sms.enabled}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 disabled:opacity-40">
            <Send className="w-3.5 h-3.5" />
            {testing === 'sms' ? 'Sender…' : 'Send test-SMS'}
          </button>
          {testResult.sms && (
            <span className={`text-sm font-medium ${testResult.sms.startsWith('✓') ? 'text-emerald-600' : 'text-red-500'}`}>
              {testResult.sms}
            </span>
          )}
        </div>
      </Section>

      {/* Teams */}
      <Section title="Microsoft Teams" icon={<Webhook className="w-4 h-4" />}
        description="Incoming Webhook til en Teams-kanal"
        badge={<EnabledBadge enabled={cfg.teams.enabled} />}>

        <Toggle value={cfg.teams.enabled} onChange={v => setTeams('enabled', v)} label="Aktivér Teams-notifikationer" />

        <Field label="Webhook URL"
          description="Teams-kanal → ... → Connectors → Incoming Webhook → Konfigurér → Kopiér URL">
          <Txt value={cfg.teams.webhook_url} onChange={v => setTeams('webhook_url', v)}
            mono placeholder="https://froekjaer.webhook.office.com/..." />
        </Field>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={() => test('teams')} disabled={testing === 'teams' || !cfg.teams.enabled}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 disabled:opacity-40">
            <Send className="w-3.5 h-3.5" />
            {testing === 'teams' ? 'Sender…' : 'Send test til Teams'}
          </button>
          {testResult.teams && (
            <span className={`text-sm font-medium ${testResult.teams.startsWith('✓') ? 'text-emerald-600' : 'text-red-500'}`}>
              {testResult.teams}
            </span>
          )}
        </div>
      </Section>

      {/* Gem */}
      <div className="flex items-center justify-between mt-6">
        <p className="text-xs text-gray-400">Indstillinger gemmes globalt — gælder for alle enheder</p>
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem indstillinger'}
        </button>
      </div>
    </div>
  )
}
