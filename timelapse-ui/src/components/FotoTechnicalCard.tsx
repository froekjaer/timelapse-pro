/**
 * TimeLapse Pro — Fototeknisk Recommendations Card
 *
 * Viser autonome optimizer anbefalinger fra Edge:
 * - Eksponeringsjusteringer (EV delta)
 * - Hvidbalance anbefalinger
 * - Fokus/depth-of-field hints
 * - Schedule avoid windows
 * - Maintenance alerts
 */

import { AlertCircle, CheckCircle, Lightbulb, Settings, Sparkles } from 'lucide-react'

interface Recommendation {
  kind: string
  action: string
  confidence: number
  reason: string
  params?: Record<string, any>
}

interface ControlPlan {
  next_capture_ev_delta: number
  commands: Array<{ type: string; command: string }>
  avoid_window_suggestion: { action: string; reason: string; duration_minutes: number } | null
  autonomous_safe_to_apply: boolean
}

interface Score {
  overall: number
  grade: 'excellent' | 'good' | 'usable' | 'needs_attention'
  exposure_penalty: number
  focus_penalty: number
  white_balance_penalty: number
  highlight_penalty: number
}

interface AutonomousData {
  engine: string
  enabled: boolean
  score?: Score
  recommendations?: Recommendation[]
  control_plan?: ControlPlan
  tags?: string[]
  observations?: Array<{ tag: string; kind: string; severity: string; description: string }>
}

interface FotoTechnicalCardProps {
  data: AutonomousData | null
  onApplyOverride?: (recommendation: Recommendation) => void
  onDismissRecommendation?: (action: string) => void
}

const KIND_ICONS: Record<string, React.ElementType> = {
  exposure: Lightbulb,
  white_balance: Sparkles,
  focus: Settings,
  depth_of_field: Settings,
  schedule: AlertCircle,
  maintenance: AlertCircle,
  framing_or_focus: Settings,
}

const KIND_LABELS: Record<string, string> = {
  exposure: 'Eksponering',
  white_balance: 'Hvidbalance',
  focus: 'Fokus',
  depth_of_field: 'Dybdeskarphed',
  schedule: 'Skema',
  maintenance: 'Vedligehold',
  framing_or_focus: 'Fokus/Framing',
}

const ACTION_LABELS: Record<string, string> = {
  increase_ev: 'Øg eksponering',
  decrease_ev: 'Sænk eksponering',
  protect_highlights: 'Beskyt highlights',
  avoid_direct_sun_window: 'Undgå direkte sol',
  run_autofocus_or_focus_slice: 'Kør autofocus',
  increase_depth_of_field: 'Øg dybdeskarphed',
  validate_focus_plane: 'Tjek fokusplan',
  set_whitebalance_daylight: 'Sæt WB: Dagslys',
  set_whitebalance_auto_or_cloudy: 'Sæt WB: Auto/Skyet',
  inspect_lens_front_glass: 'Inspicer frontglas',
  inspect_for_snow_dirt_or_condensation: 'Tjek sne/snavs/dug',
}

const GRADE_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  excellent: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: '🌟' },
  good: { bg: 'bg-sky-50', text: 'text-sky-700', icon: '👍' },
  usable: { bg: 'bg-amber-50', text: 'text-amber-700', icon: '⚠️' },
  needs_attention: { bg: 'bg-red-50', text: 'text-red-700', icon: '🔴' },
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'text-emerald-600'
  if (confidence >= 0.70) return 'text-sky-600'
  if (confidence >= 0.55) return 'text-amber-600'
  return 'text-gray-500'
}

function formatEV(ev: number): string {
  if (ev === 0) return '0'
  const sign = ev > 0 ? '+' : ''
  return `${sign}${ev.toFixed(1)} EV`
}

export function FotoTechnicalCard({ data, onApplyOverride, onDismissRecommendation }: FotoTechnicalCardProps) {
  if (!data || !data.enabled) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-500">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4" />
          <span>Fototeknisk AI er deaktiveret</span>
        </div>
      </div>
    )
  }

  const score = data.score
  const recommendations = data.recommendations || []
  const control = data.control_plan
  const observations = data.observations || []
  const tags = data.tags || []

  return (
    <div className="space-y-4">
      {/* Score Card */}
      {score && (
        <div className={`border rounded-lg p-4 ${GRADE_COLORS[score.grade || 'usable'].bg}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{GRADE_COLORS[score.grade].icon}</span>
              <div>
                <div className={`font-semibold ${GRADE_COLORS[score.grade].text}`}>
                  {score.grade === 'excellent' && 'Fremragende kvalitet'}
                  {score.grade === 'good' && 'God kvalitet'}
                  {score.grade === 'usable' && 'Brugbar kvalitet'}
                  {score.grade === 'needs_attention' && 'Kræver opmærksomhed'}
                </div>
                <div className={`text-2xl font-bold ${GRADE_COLORS[score.grade].text}`}>
                  {score.overall.toFixed(1)}%
                </div>
              </div>
            </div>
            <div className="text-xs text-gray-500 text-right">
              <div>Eksponering: -{score.exposure_penalty.toFixed(1)}p</div>
              <div>Fokus: -{score.focus_penalty.toFixed(1)}p</div>
              <div>WB: -{score.white_balance_penalty.toFixed(1)}p</div>
              <div>Highlights: -{score.highlight_penalty.toFixed(1)}p</div>
            </div>
          </div>
        </div>
      )}

      {/* Control Plan Status */}
      {control && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="font-semibold text-sm text-gray-800 mb-3 flex items-center gap-2">
            <Settings className="w-4 h-4" />
            Kontrolplan
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Næste capture EV justering:</span>
              <span className={`font-semibold ${control.next_capture_ev_delta !== 0 ? 'text-sky-600' : 'text-gray-400'}`}>
                {formatEV(control.next_capture_ev_delta)}
              </span>
            </div>
            {control.commands.length > 0 && (
              <div className="text-gray-600">
                <span className="font-medium">Aktive kommandoer:</span>
                <ul className="mt-1 space-y-1">
                  {control.commands.map((cmd, i) => (
                    <li key={i} className="text-xs text-sky-600">
                      {cmd.type}: {cmd.command}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {control.avoid_window_suggestion && (
              <div className="flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded">
                <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5" />
                <div className="text-xs">
                  <div className="font-medium text-amber-800">Avoid Window anbefaling</div>
                  <div className="text-amber-700">
                    {control.avoid_window_suggestion.reason} ({control.avoid_window_suggestion.duration_minutes} min)
                  </div>
                </div>
              </div>
            )}
            <div className="flex items-center gap-2">
              {control.autonomous_safe_to_apply ? (
                <CheckCircle className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600" />
              )}
              <span className="text-xs text-gray-600">
                {control.autonomous_safe_to_apply
                  ? 'Kan anvendes automatisk'
                  : 'Kræver manuel godkendelse'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Observations */}
      {observations.length > 0 && (
        <div className="bg-sky-50 border border-sky-100 rounded-lg p-4">
          <h4 className="font-semibold text-sm text-sky-800 mb-2">Observationer</h4>
          <div className="space-y-2">
            {observations.map((obs, i) => (
              <div key={i} className="text-xs text-sky-700">
                <span className="font-medium">{obs.tag}:</span> {obs.description}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="font-semibold text-sm text-gray-800 mb-3 flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-500" />
            Anbefalinger ({recommendations.length})
          </h4>
          <div className="space-y-2">
            {recommendations.map((rec, i) => {
              const Icon = KIND_ICONS[rec.kind] || Lightbulb
              return (
                <div
                  key={i}
                  className="p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2 flex-1 min-w-0">
                      <Icon className="w-4 h-4 text-sky-500 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm text-gray-800 truncate">
                          {ACTION_LABELS[rec.action] || rec.action}
                        </div>
                        <div className="text-xs text-gray-600 mt-0.5">{rec.reason}</div>
                        {rec.params && Object.keys(rec.params).length > 0 && (
                          <div className="mt-1 text-xs text-gray-500">
                            {Object.entries(rec.params).map(([k, v]) => (
                              <span key={k} className="mr-2">
                                {k}: {typeof v === 'number' ? v.toFixed(2) : String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <div className={`text-xs font-semibold ${confidenceColor(rec.confidence)}`}>
                        {(rec.confidence * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-gray-400">{KIND_LABELS[rec.kind] || rec.kind}</div>
                      {onDismissRecommendation && (
                        <button
                          onClick={() => onDismissRecommendation(rec.action)}
                          className="text-xs text-gray-400 hover:text-gray-600 underline"
                        >
                          Ignorer
                        </button>
                      )}
                    </div>
                  </div>
                  {onApplyOverride && rec.kind !== 'maintenance' && (
                    <button
                      onClick={() => onApplyOverride(rec)}
                      className="mt-2 w-full py-1.5 text-xs bg-sky-500 text-white rounded hover:bg-sky-600 transition-colors"
                    >
                      Anvend nu
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Tags */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map((tag, i) => (
            <span
              key={i}
              className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
