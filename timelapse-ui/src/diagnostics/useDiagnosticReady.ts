import { useEffect } from 'react'
import { frameReady, loadFailed, phase } from './timingRecorder'

export function useDiagnosticReady(loading: boolean, label: string, error?: unknown) {
  useEffect(() => {
    if (loading) { phase(`${label}-data-wait`); return }
    // A loading state that ended with an error is not a successful page load.
    if (error) { loadFailed(label); return }
    return frameReady(label)
  }, [loading, label, error])
}
