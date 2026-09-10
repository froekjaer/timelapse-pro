import { useEffect } from 'react'
import { frameReady, phase } from './timingRecorder'

export function useDiagnosticReady(loading: boolean, label: string) {
  useEffect(() => {
    if (loading) { phase(`${label}-data-wait`); return }
    return frameReady(label)
  }, [loading, label])
}
