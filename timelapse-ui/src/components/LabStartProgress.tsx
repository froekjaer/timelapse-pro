// LAB start, step by step (Peter 2026-10-10: "feedback step, når man har
// trykket start lab, så man kan se at der sker noget, og hvor langt den er").
// Steps come from the Headend (tunnel wake) and the Edge itself, via
// GET /api/edge/lab-progress/{device} — real events, not a guessed countdown.
import { useEffect, useState } from 'react'
import { CheckCircle, Circle, Loader2, XCircle } from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

interface ProgressEvent {
  phase: string
  detail: string
  at: string
  extra?: { warmup_s?: number }
}

const STEPS: { phase: string; label: string }[] = [
  { phase: 'requested', label: 'Anmodning sendt' },
  { phase: 'woken', label: 'Edge vækket gennem SSH-tunnel' },
  { phase: 'received', label: 'Edge har modtaget LAB' },
  { phase: 'camera_power', label: 'Kameraet tændes og varmer op' },
  { phase: 'camera_connecting', label: 'Forbinder til kameraet' },
  { phase: 'ready', label: 'Kameraet er klar' },
  { phase: 'params', label: 'Kameraparametre hentet' },
]

export function LabStartProgress({ deviceId, since }: { deviceId: string; since: string | null }) {
  const [events, setEvents] = useState<ProgressEvent[]>([])
  // Server-clock "now", refreshed with every poll (no Date.now() during render).
  const [now, setNow] = useState(() => (since ? new Date(since).getTime() : 0))

  useEffect(() => {
    if (!since) return
    let alive = true
    const poll = async () => {
      try {
        const r = await fetch(`${getApiUrl()}/api/edge/lab-progress/${pathSegment(deviceId)}?since=${encodeURIComponent(since)}`,
          { credentials: 'include' })
        if (!r.ok || !alive) return
        const data = await r.json()
        setEvents(data.events ?? [])
        if (data.server_time) setNow(new Date(data.server_time).getTime())
      } catch { /* keep the last known steps */ }
    }
    poll()
    const iv = window.setInterval(poll, 1000)
    return () => { alive = false; window.clearInterval(iv) }
  }, [deviceId, since])

  const last = (phase: string) => [...events].reverse().find(e => e.phase === phase)
  const failed = last('camera_failed')
  const retry = last('camera_retry')
  // Highest step reported so far. Steps before it are done; the warm-up and
  // connect steps stay "in progress" until the next step arrives; after a
  // finished step the next one is the current (spinning) one.
  const reached = STEPS.reduce((acc, s, i) => (s.phase === 'requested' || last(s.phase) ? i : acc), 0)
  const inProgress = new Set(['camera_power', 'camera_connecting'])
  const stateOf = (i: number): 'done' | 'current' | 'pending' => {
    if (i < reached) return 'done'
    if (i === reached) return inProgress.has(STEPS[i].phase) && !failed ? 'current' : 'done'
    if (i === reached + 1 && !failed && !inProgress.has(STEPS[reached].phase)) return 'current'
    return 'pending'
  }
  const elapsed = since ? Math.max(0, Math.round((now - new Date(since).getTime()) / 1000)) : 0

  return (
    <div className="max-w-md mx-auto mt-10 bg-white border border-gray-200 rounded-2xl p-5 text-left">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-700">LAB starter</h2>
        <span className="text-xs text-gray-400">{elapsed} s</span>
      </div>
      <ol className="space-y-2.5">
        {STEPS.map((step, i) => {
          const event = last(step.phase)
          const state = stateOf(i)
          const done = state === 'done'
          const current = state === 'current'
          let note = ''
          if (current && step.phase === 'camera_power' && event) {
            const left = Math.ceil((event.extra?.warmup_s ?? 0) - (now - new Date(event.at).getTime()) / 1000)
            note = left > 0 ? `opvarmning ${left} s` : 'venter på kameraet'
          }
          if (current && retry && step.phase === 'camera_connecting') note = retry.detail
          return (
            <li key={step.phase} className="flex items-start gap-2.5 text-sm">
              {done ? <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                : current ? <Loader2 className="w-4 h-4 text-purple-500 animate-spin mt-0.5 shrink-0" />
                : <Circle className="w-4 h-4 text-gray-300 mt-0.5 shrink-0" />}
              <span className={done ? 'text-gray-700' : current ? 'text-purple-700 font-medium' : 'text-gray-400'}>
                {step.label}
                {done && event && since && (
                  <span className="text-xs text-gray-400 ml-2">
                    +{Math.max(0, Math.round((new Date(event.at).getTime() - new Date(since).getTime()) / 1000))} s
                  </span>
                )}
                {note && <span className="block text-xs text-gray-500 font-normal">{note}</span>}
              </span>
            </li>
          )
        })}
        {failed && (
          <li className="flex items-start gap-2.5 text-sm text-red-600">
            <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>Kameraet kunne ikke startes<span className="block text-xs">{failed.detail}</span></span>
          </li>
        )}
      </ol>
      {!events.length && elapsed > 20 && (
        <p className="text-xs text-amber-600 mt-4">
          Intet svar fra Edgen endnu. Er SSH-tunnelen oppe? Uden tunnel hentes LAB først ved næste normale poll (op til 5 min).
        </p>
      )}
    </div>
  )
}
