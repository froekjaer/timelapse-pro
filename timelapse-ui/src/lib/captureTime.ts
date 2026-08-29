import type { Capture } from '../types'

const LOCAL_CAPTURE_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/
const EXPLICIT_TZ_RE = /(Z|[+-]\d{2}:?\d{2})$/i

const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

function captureTimestampSource(capture: Pick<Capture, 'captured_at' | 'captured_at_local'>): string | null {
  return capture.captured_at_local ?? capture.captured_at ?? null
}

export function formatCaptureTimestamp(
  capture: Pick<Capture, 'captured_at' | 'captured_at_local'>,
  options: { includeYear?: boolean; timeOnly?: boolean } = {},
): string {
  const raw = captureTimestampSource(capture)
  if (!raw) return '–'
  const localMatch = raw.match(LOCAL_CAPTURE_RE)
  if (localMatch && !EXPLICIT_TZ_RE.test(raw)) {
    const [, year, month, day, hour, minute] = localMatch
    if (options.timeOnly) return `${hour}.${minute}`
    return options.includeYear ? `${day}.${month}.${year} ${hour}.${minute}` : `${day}.${month}. ${hour}.${minute}`
  }
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return raw
  if (options.timeOnly) {
    return parsed.toLocaleTimeString('da-DK', { timeZone: getTz(), hour: '2-digit', minute: '2-digit' })
  }
  return parsed.toLocaleString('da-DK', {
    timeZone: getTz(),
    day: '2-digit',
    month: '2-digit',
    ...(options.includeYear ? { year: 'numeric' as const } : {}),
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function captureTimestampParts(capture: Pick<Capture, 'captured_at' | 'captured_at_local'>) {
  const raw = captureTimestampSource(capture)
  const localMatch = raw?.match(LOCAL_CAPTURE_RE)
  if (raw && localMatch && !EXPLICIT_TZ_RE.test(raw)) {
    const [, year, month, day, hour, minute] = localMatch
    return { datePart: `${day}.${month}.`, yearPart: year, timePart: `${hour}.${minute}`, time: `${day}.${month}. ${hour}.${minute}` }
  }
  const time = formatCaptureTimestamp(capture)
  const [datePart, timePart] = time.split(', ')
  const yearPart = raw ? formatCaptureTimestamp(capture, { includeYear: true }).match(/\d{4}/)?.[0] ?? '' : ''
  return { datePart, yearPart, timePart: timePart ?? '', time }
}
