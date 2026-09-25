import {
  Activity,
  ArrowDown,
  ArrowUp,
  Brain,
  CheckCircle,
  Cloud,
  Cpu,
  Minus,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
} from 'lucide-react'

export type ProviderName = 'apple' | 'ollama' | 'gemini'

export interface ProviderAvailability {
  available: boolean
  reason?: string | null
  model?: string
  execution?: string
  location?: string | null
}

export interface ProviderStatusItem {
  configured: boolean
  capabilities: string[]
  error_type?: string
  availability?: ProviderAvailability
}

export interface ProviderStatusSnapshot {
  providers: Record<string, ProviderStatusItem>
  policies: Record<string, string[]>
  image_strategies: Record<string, { primary: string | null; escalation: string | null }>
}

export interface ProviderOrderField {
  key: string
  label: string
  value: string
  default: string
}

interface Props {
  fields: ProviderOrderField[]
  status: ProviderStatusSnapshot | null
  probing: boolean
  saving: boolean
  onProbe: () => void
  onChange: (key: string, value: string) => void
  onSave: () => void
}

const PROVIDERS: ProviderName[] = ['apple', 'ollama', 'gemini']

const PROVIDER_META = {
  apple: {
    label: 'Apple Intelligence',
    short: 'Apple',
    description: 'Foundation Models på Headend · lokal behandling',
    icon: Brain,
    accent: 'border-violet-700/60 bg-violet-950/35',
    iconClass: 'text-violet-300',
  },
  ollama: {
    label: 'Ollama',
    short: 'Ollama',
    description: 'Lokale modeller på Headend · offline-capable',
    icon: Cpu,
    accent: 'border-emerald-800/60 bg-emerald-950/25',
    iconClass: 'text-emerald-300',
  },
  gemini: {
    label: 'Gemini',
    short: 'Gemini',
    description: 'Vertex AI · cloud · EU-region når konfigureret',
    icon: Cloud,
    accent: 'border-sky-800/60 bg-sky-950/25',
    iconClass: 'text-sky-300',
  },
} as const

const POLICY_META: Record<string, { title: string; description: string }> = {
  ai_provider_search_order: {
    title: 'AI Search',
    description: 'Fortolker naturlige søgninger til sikre TimeLapse-filtre.',
  },
  ai_provider_siem_order: {
    title: 'SIEM AI',
    description: 'Forklarer og korrelerer hændelser. Deterministiske alarmer er stadig autoritative.',
  },
  ai_provider_aiops_order: {
    title: 'AI Ops',
    description: 'Analyserer driftsstatus og foreslår næste undersøgelser.',
  },
  ai_provider_cmdb_order: {
    title: 'CMDB AI',
    description: 'Strukturerer og beriger inventar- og konfigurationsdata.',
  },
  ai_provider_summarization_order: {
    title: 'Opsummering',
    description: 'Genererer korte forklaringer og resuméer til UI og drift.',
  },
}

function parseOrder(value: string): ProviderName[] {
  const parsed = String(value || '')
    .split(',')
    .map(item => item.trim().toLowerCase())
    .filter((item): item is ProviderName => PROVIDERS.includes(item as ProviderName))
  return [...new Set(parsed)]
}

function statusLabel(item?: ProviderStatusItem) {
  if (!item?.configured) {
    return { label: 'Ikke konfigureret', className: 'text-slate-500', dot: 'bg-slate-600' }
  }
  if (item.availability?.available === true) {
    return { label: 'Klar', className: 'text-emerald-300', dot: 'bg-emerald-400' }
  }
  if (item.availability?.available === false) {
    return { label: 'Ikke tilgængelig', className: 'text-red-300', dot: 'bg-red-400' }
  }
  return { label: 'Konfigureret', className: 'text-amber-300', dot: 'bg-amber-400' }
}

function ProviderStatusCard({ name, item }: { name: ProviderName; item?: ProviderStatusItem }) {
  const meta = PROVIDER_META[name]
  const Icon = meta.icon
  const state = statusLabel(item)
  const availability = item?.availability

  return (
    <div className={`rounded-xl border p-4 ${meta.accent}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="rounded-lg border border-white/10 bg-black/15 p-2">
            <Icon className={`h-4 w-4 ${meta.iconClass}`} />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white">{meta.label}</h3>
            <p className="mt-1 text-xs leading-5 text-slate-400">{meta.description}</p>
          </div>
        </div>
        <span className={`inline-flex shrink-0 items-center gap-1.5 text-xs ${state.className}`}>
          <span className={`h-2 w-2 rounded-full ${state.dot}`} />
          {state.label}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {(item?.capabilities || []).filter(cap => !cap.endsWith('_execution')).map(capability => (
          <span key={capability} className="rounded-full border border-white/8 bg-black/15 px-2 py-0.5 text-[11px] text-slate-400">
            {capability}
          </span>
        ))}
      </div>

      {availability && (
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500">
          {availability.model && <span>model <span className="font-mono text-slate-400">{availability.model}</span></span>}
          {availability.location && <span>region <span className="font-mono text-slate-400">{availability.location}</span></span>}
          {!availability.available && availability.reason && (
            <span className="text-red-300/80">{availability.reason}</span>
          )}
        </div>
      )}
    </div>
  )
}

function ProviderChainEditor({
  field,
  status,
  onChange,
}: {
  field: ProviderOrderField
  status: ProviderStatusSnapshot | null
  onChange: (value: string) => void
}) {
  const current = parseOrder(field.value)
  const order = current.length ? current : parseOrder(field.default)
  const inactive = PROVIDERS.filter(provider => !order.includes(provider))

  const commit = (next: ProviderName[]) => {
    if (!next.length) return
    onChange(next.join(','))
  }

  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta
    if (target < 0 || target >= order.length) return
    const next = [...order]
    const [provider] = next.splice(index, 1)
    next.splice(target, 0, provider)
    commit(next)
  }

  const remove = (provider: ProviderName) => {
    if (order.length <= 1) return
    commit(order.filter(item => item !== provider))
  }

  const add = (provider: ProviderName) => commit([...order, provider])

  const meta = POLICY_META[field.key] || { title: field.label, description: '' }
  const unavailable = order.filter(provider => {
    const item = status?.providers?.[provider]
    return item?.configured === false || item?.availability?.available === false
  })

  return (
    <div className="rounded-xl border border-white/8 bg-gray-950/35 p-4">
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-violet-300" />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-white">{meta.title}</h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">{meta.description}</p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {order.map((provider, index) => {
          const providerMeta = PROVIDER_META[provider]
          const Icon = providerMeta.icon
          const item = status?.providers?.[provider]
          const state = statusLabel(item)
          return (
            <div key={provider} className="flex items-center gap-2 rounded-lg border border-white/8 bg-gray-900 px-3 py-2.5">
              <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                index === 0 ? 'bg-violet-600 text-white' : 'bg-gray-800 text-slate-400'
              }`}>
                {index + 1}
              </div>
              <Icon className={`h-4 w-4 shrink-0 ${providerMeta.iconClass}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className="text-sm font-medium text-slate-200">{providerMeta.short}</span>
                  <span className="text-[11px] uppercase tracking-wide text-slate-600">
                    {index === 0 ? 'Primær' : `Fallback ${index}`}
                  </span>
                  <span className={`inline-flex items-center gap-1 text-[11px] ${state.className}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${state.dot}`} />
                    {state.label}
                  </span>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => move(index, -1)}
                  disabled={index === 0}
                  aria-label={`Flyt ${providerMeta.label} op`}
                  title="Højere prioritet"
                  className="rounded-md border border-white/8 p-1.5 text-slate-400 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-25"
                >
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => move(index, 1)}
                  disabled={index === order.length - 1}
                  aria-label={`Flyt ${providerMeta.label} ned`}
                  title="Lavere prioritet"
                  className="rounded-md border border-white/8 p-1.5 text-slate-400 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-25"
                >
                  <ArrowDown className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => remove(provider)}
                  disabled={order.length <= 1}
                  aria-label={`Fjern ${providerMeta.label}`}
                  title={order.length <= 1 ? 'Mindst én provider er påkrævet' : 'Fjern fra denne policy'}
                  className="rounded-md border border-white/8 p-1.5 text-slate-500 hover:border-red-800 hover:bg-red-950/30 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-25"
                >
                  <Minus className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {inactive.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-slate-600">Tilføj fallback:</span>
          {inactive.map(provider => {
            const metaProvider = PROVIDER_META[provider]
            const item = status?.providers?.[provider]
            const disabled = item?.configured === false
            return (
              <button
                key={provider}
                type="button"
                onClick={() => add(provider)}
                disabled={disabled}
                title={disabled ? `${metaProvider.label} er ikke konfigureret` : `Tilføj ${metaProvider.label} som sidste fallback`}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-gray-900 px-2.5 py-1 text-xs text-slate-400 hover:border-violet-700 hover:text-violet-200 disabled:cursor-not-allowed disabled:opacity-35"
              >
                <Plus className="h-3 w-3" />
                {metaProvider.short}
              </button>
            )
          })}
        </div>
      )}

      {unavailable.length > 0 && (
        <p className="mt-3 text-xs leading-5 text-amber-300/80">
          {unavailable.map(provider => PROVIDER_META[provider].short).join(', ')} er ikke klar lige nu.
          Routeren fortsætter til næste fallback, hvis den valgte provider ikke kan bruges.
        </p>
      )}
    </div>
  )
}

export function AIProviderPolicyPanel({
  fields,
  status,
  probing,
  saving,
  onProbe,
  onChange,
  onSave,
}: Props) {
  return (
    <section className="rounded-xl border border-violet-800/30 bg-gray-900 p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <div className="rounded-lg border border-violet-800/40 bg-violet-950/50 p-2">
            <Activity className="h-4 w-4 text-violet-300" />
          </div>
          <div>
            <h2 className="font-semibold">Provider-politik</h2>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
              Vælg hvilken provider hver tekst/structured-funktion prøver først, og rækkefølgen på fallbacks.
              Billedanalyse vælges fortsat pr. kunde/site på fanen Strategi. Ændringen påvirker kun nye kald.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onProbe}
            disabled={probing}
            className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/10 bg-gray-950/50 px-3 py-2 text-sm text-slate-300 hover:bg-white/5 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${probing ? 'animate-spin' : ''}`} />
            {probing ? 'Tester…' : 'Test forbindelser'}
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="inline-flex min-h-10 items-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Gem provider-politik
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {PROVIDERS.map(provider => (
          <ProviderStatusCard key={provider} name={provider} item={status?.providers?.[provider]} />
        ))}
      </div>

      <div className="mt-5 grid gap-3 xl:grid-cols-2">
        {fields.map(field => (
          <ProviderChainEditor
            key={field.key}
            field={field}
            status={status}
            onChange={value => onChange(field.key, value)}
          />
        ))}
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-lg border border-emerald-900/40 bg-emerald-950/20 px-3 py-2.5 text-xs leading-5 text-slate-400">
        <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
        <span>
          Provider-rækkefølgen er policy — ikke business logic. TimeLapse beholder RBAC, tenant-scope,
          canonical vocabulary, GDPR-policy og deterministiske alarmer uanset hvilken provider der vælges.
        </span>
      </div>
    </section>
  )
}
