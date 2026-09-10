import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { diagnosticsEnabled, enableDiagnostics, phase, report, stopDiagnostics } from './timingRecorder'

export function DiagnosticFallback() {
  useEffect(() => { phase('route-module-wait'); return () => phase('route-module-resolved') }, [])
  return null
}
export function NavigationDiagnostics() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [enabled, setEnabled] = useState(diagnosticsEnabled)
  const [text, setText] = useState('')
  useEffect(() => { phase('route-committed') }, [pathname])
  useEffect(() => {
    if (!user) stopDiagnostics()
  }, [user])
  if (!user || !['admin', 'super_admin'].includes(user.role)) return null
  return <details className="mx-auto max-w-7xl px-4 py-2 text-sm text-slate-600">
    <summary>Fejlsøg ventetid{enabled ? ' — måling aktiv' : ''}</summary>
    <p>Måler kun i denne fane. Ingen billeder eller loginoplysninger gemmes. Rapporten sendes ikke automatisk.</p>
    {!enabled ? <button onClick={() => { if (!enableDiagnostics()) setText('Browseren tillader ikke lokal lagring.') }}>Start måling og genindlæs</button> : <>
      <button className="mr-4" onClick={() => setText(report())}>Vis tidsrapport</button>
      <button className="mr-4" onClick={() => {
        const url = URL.createObjectURL(new Blob([report()], { type: 'application/json' }))
        const a = document.createElement('a'); a.href = url; a.download = 'timelapse-navigation.json'; a.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }}>Hent tidsrapport</button>
      <button onClick={() => { stopDiagnostics(); setEnabled(false); setText('') }}>Stop og slet måling</button>
    </>}
    {text && <textarea aria-label="Tidsrapport" readOnly value={text} className="mt-2 h-64 w-full font-mono text-xs" />}
  </details>
}
