/**
 * TimeLapse Pro — Site-Wide Look Matching Card
 *
 * Viser site-wide look matching status og muligheder:
 * - Site reference frame status (oprettet/mangler)
 * - Per-kamera LUT status
 * - Capture hints (WB, Picture Control, EV)
 * - Match quality scores
 * - Kamera-specifikke anbefalinger (Nikon Picture Control, Canon Picture Styles)
 */

import { CheckCircle, AlertCircle, Camera, Sparkles, Eye, Target, Info } from 'lucide-react'

interface ReferenceInfo {
  site_id: string
  created_at: string
  created_by_camera: string
  quality_score: number
  scene_type: string
  picture_control: string
}

interface LUTInfo {
  camera_model: string
  generated_at: string
  match_quality: number
  exposure_offset_ev: number
  saturation_multiplier: number
  picture_control_hint: string
}

interface CaptureHints {
  has_reference: boolean
  picture_control: string
  parameters?: Record<string, number>
  wb_kelvin_hint?: number | null
  wb_tint_hint?: number
  ev_hint?: number
  match_quality?: number
}

interface SiteLookData {
  enabled: boolean
  has_site_reference: boolean
  is_site_reference?: boolean
  lut_generated?: boolean
  capture_hints?: CaptureHints
  reference_info?: ReferenceInfo | null
  lut_info?: LUTInfo | null
  error?: string
}

interface SiteLookCardProps {
  data: SiteLookData | null
  cameraModel?: string
  onSetReference?: () => void
  onRegenerateLUT?: () => void
}

const SCENE_LABELS: Record<string, string> = {
  day: 'Dagtid',
  golden_hour: 'Gyldent time',
  overcast: 'Overskyet',
  night: 'Nat',
  unknown: 'Ukendt',
}

const PICTURE_CONTROL_ICONS: Record<string, string> = {
  Flat: '🎬',
  Standard: '📷',
  Neutral: '⚖️',
  Vivid: '🌈',
  Monochrome: '⬛',
  Portrait: '👤',
  Landscape: '🏞️',
  Faithful: '🎯',
}

function matchQualityColor(quality: number): string {
  if (quality >= 0.90) return 'text-emerald-600'
  if (quality >= 0.75) return 'text-sky-600'
  if (quality >= 0.60) return 'text-amber-600'
  return 'text-red-600'
}

function formatEV(ev: number): string {
  if (ev === 0) return '0'
  const sign = ev > 0 ? '+' : ''
  return `${sign}${ev.toFixed(2)} EV`
}

export function SiteLookCard({ data, cameraModel = 'Unknown', onSetReference, onRegenerateLUT }: SiteLookCardProps) {
  if (!data || !data.enabled) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-500">
        <div className="flex items-center gap-2">
          <Camera className="w-4 h-4" />
          <span>Site-wide look matching er deaktiveret</span>
        </div>
      </div>
    )
  }

  const hasError = data.error
  const hasReference = data.has_site_reference
  const isReference = data.is_site_reference
  const hasLUT = data.lut_generated
  const hints = data.capture_hints
  const refInfo = data.reference_info
  const lutInfo = data.lut_info

  return (
    <div className="space-y-4">
      {/* Status Header */}
      <div className={`border rounded-lg p-4 ${hasReference ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {hasReference ? (
              <CheckCircle className="w-5 h-5 text-emerald-600" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-600" />
            )}
            <div>
              <div className={`font-semibold ${hasReference ? 'text-emerald-800' : 'text-amber-800'}`}>
                {hasReference ? 'Site Reference Aktiv' : 'Mangler Site Reference'}
              </div>
              <div className="text-xs text-gray-600">
                {hasReference
                  ? 'Alle kameraer matcher til fælles reference'
                  : 'Kameraer arbejder uafhængigt - videoer kan have forskellig look'}
              </div>
            </div>
          </div>
          {isReference && (
            <div className="text-xs bg-emerald-100 text-emerald-800 px-2 py-1 rounded-full">
              ✨ Denne billede er reference
            </div>
          )}
        </div>
      </div>

      {/* Error Display */}
      {hasError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="flex items-center gap-2 text-red-800">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm font-medium">Fejl under look matching:</span>
          </div>
          <div className="text-xs text-red-700 mt-1">{data.error}</div>
        </div>
      )}

      {/* Reference Info */}
      {refInfo && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="font-semibold text-sm text-gray-800 mb-3 flex items-center gap-2">
            <Target className="w-4 h-4 text-emerald-500" />
            Site Reference Info
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Site ID:</span>
              <span className="font-medium text-gray-900">{refInfo.site_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Oprettet af:</span>
              <span className="font-medium text-gray-900">{refInfo.created_by_camera}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Kvalitetsscore:</span>
              <span className={`font-semibold ${refInfo.quality_score >= 85 ? 'text-emerald-600' : 'text-sky-600'}`}>
                {refInfo.quality_score.toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Scene type:</span>
              <span className="text-gray-900">{SCENE_LABELS[refInfo.scene_type] || refInfo.scene_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Picture Control:</span>
              <span className="text-gray-900">
                {PICTURE_CONTROL_ICONS[refInfo.picture_control]} {refInfo.picture_control}
              </span>
            </div>
            <div className="text-xs text-gray-500 mt-2">
              Oprettet: {new Date(refInfo.created_at).toLocaleString('da-DK')}
            </div>
          </div>
        </div>
      )}

      {/* LUT Info */}
      {lutInfo && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="font-semibold text-sm text-gray-800 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-sky-500" />
            Kamera LUT (Look Matching)
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Kamera model:</span>
              <span className="font-medium text-gray-900">{lutInfo.camera_model}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Match kvalitet:</span>
              <span className={`font-semibold ${matchQualityColor(lutInfo.match_quality)}`}>
                {(lutInfo.match_quality * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Eksponering offset:</span>
              <span className={`font-medium ${Math.abs(lutInfo.exposure_offset_ev) > 0.1 ? 'text-amber-600' : 'text-gray-900'}`}>
                {formatEV(lutInfo.exposure_offset_ev)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Saturation multiplier:</span>
              <span className={`font-medium ${Math.abs(lutInfo.saturation_multiplier - 1.0) > 0.05 ? 'text-amber-600' : 'text-gray-900'}`}>
                {lutInfo.saturation_multiplier.toFixed(3)}x
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Picture Control hint:</span>
              <span className="text-gray-900">
                {PICTURE_CONTROL_ICONS[lutInfo.picture_control_hint]} {lutInfo.picture_control_hint}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Capture Hints */}
      {hints && (
        <div className="bg-sky-50 border border-sky-100 rounded-lg p-4">
          <h4 className="font-semibold text-sm text-sky-800 mb-3 flex items-center gap-2">
            <Eye className="w-4 h-4" />
            Capture Hints (Næste optagelse)
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-sky-700">Picture Control:</span>
              <span className="font-medium text-sky-900">
                {PICTURE_CONTROL_ICONS[hints.picture_control]} {hints.picture_control}
              </span>
            </div>
            {hints.wb_kelvin_hint && (
              <div className="flex justify-between items-center">
                <span className="text-sky-700">White Balance hint:</span>
                <span className="font-medium text-sky-900">{hints.wb_kelvin_hint}K</span>
              </div>
            )}
            {hints.ev_hint !== undefined && Math.abs(hints.ev_hint) > 0.01 && (
              <div className="flex justify-between items-center">
                <span className="text-sky-700">Eksponering hint:</span>
                <span className={`font-medium ${hints.ev_hint > 0 ? 'text-amber-600' : 'text-sky-900'}`}>
                  {formatEV(hints.ev_hint)}
                </span>
              </div>
            )}
            {hints.parameters && Object.keys(hints.parameters).length > 0 && (
              <div className="mt-3 pt-3 border-t border-sky-200">
                <div className="text-xs text-sky-700 mb-1">Picture Control parametre:</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(hints.parameters).map(([key, value]) => (
                    <span key={key} className="px-2 py-1 bg-white rounded text-xs text-sky-800">
                      {key}: {value}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Camera-Specific Info */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="font-semibold text-sm text-gray-800 mb-2 flex items-center gap-2">
          <Camera className="w-4 h-4 text-gray-500" />
          Kamera-specifikke Anbefalinger
        </h4>
        <div className="text-sm text-gray-600">
          <div className="flex justify-between items-center">
            <span>Dette kamera:</span>
            <span className="font-medium text-gray-900">{cameraModel}</span>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            {cameraModel.toLowerCase().includes('nikon') && (
              <div className="flex items-center gap-1">
                <Info className="w-3 h-3" />
                <span>Nikon Picture Controls: Flat anbefales for maksimal dynamisk område og post-processing fleksibilitet. Standard giver god out-of-camera kvalitet.</span>
              </div>
            )}
            {cameraModel.toLowerCase().includes('canon') && (
              <div className="flex items-center gap-1">
                <Info className="w-3 h-3" />
                <span>Canon Picture Styles: Neutral anbefales for maksimal dynamisk område. Standard giver god out-of-camera kvalitet.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        {!hasReference && onSetReference && (
          <button
            onClick={onSetReference}
            className="flex-1 py-2 px-4 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium"
          >
            Opret Site Reference
          </button>
        )}
        {hasReference && onRegenerateLUT && (
          <button
            onClick={onRegenerateLUT}
            className="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors text-sm font-medium"
          >
            Regenerer Kamera LUT
          </button>
        )}
      </div>
    </div>
  )
}
