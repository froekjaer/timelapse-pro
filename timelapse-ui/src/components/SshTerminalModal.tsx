import { useEffect, useRef, useState } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { X } from 'lucide-react'
import { getApiUrl } from '../api/client'

const RESIZE_PREFIX = '\x01RESIZE:'

interface TerminalSession {
  session_id: string
  websocket_path: string
  expires_at: string
  host_fingerprint: string
  identity_key_path: string
  remote_port: number
}

async function startTerminalSession(deviceId: string): Promise<TerminalSession> {
  const res = await fetch(`${getApiUrl()}/api/admin/ssh-tunnel/${encodeURIComponent(deviceId)}/terminal-sessions`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Terminal afvist (${res.status})`)
  }
  return res.json()
}

function websocketUrl(path: string) {
  const apiUrl = getApiUrl()
  const url = new URL(path, apiUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

export function SshTerminalModal({ deviceId, onClose }: { deviceId: string; onClose: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [session, setSession] = useState<TerminalSession | null>(null)

  useEffect(() => {
    let cancelled = false
    let ws: WebSocket | null = null
    let term: XTerm | null = null
    let fitAddon: FitAddon | null = null

    async function open() {
      try {
        const created = await startTerminalSession(deviceId)
        if (cancelled) return
        setSession(created)
        if (!containerRef.current) return

        term = new XTerm({
          cursorBlink: true,
          fontSize: 13,
          fontFamily: '"SF Mono", Menlo, Monaco, monospace',
          theme: { background: '#0b1020', foreground: '#dbeafe' },
        })
        fitAddon = new FitAddon()
        term.loadAddon(fitAddon)
        term.open(containerRef.current)
        fitAddon.fit()

        ws = new WebSocket(websocketUrl(created.websocket_path))
        const sendResize = () => {
          if (ws?.readyState === WebSocket.OPEN && term) ws.send(`${RESIZE_PREFIX}${term.cols},${term.rows}`)
        }

        ws.onopen = () => {
          term?.write(`\x1b[36mForbinder til ${deviceId} via verified reverse tunnel...\x1b[0m\r\n`)
          sendResize()
        }
        ws.onmessage = ev => term?.write(String(ev.data))
        ws.onerror = () => term?.write('\r\n\x1b[31m[Terminalforbindelse fejlede]\x1b[0m\r\n')
        ws.onclose = () => term?.write('\r\n\x1b[33m[Terminal lukket]\x1b[0m\r\n')

        const dataDisposable = term.onData(data => {
          if (ws?.readyState === WebSocket.OPEN) ws.send(data)
        })
        const handleResize = () => {
          fitAddon?.fit()
          sendResize()
        }
        window.addEventListener('resize', handleResize)
        const observer = new ResizeObserver(handleResize)
        observer.observe(containerRef.current)

        return () => {
          window.removeEventListener('resize', handleResize)
          observer.disconnect()
          dataDisposable.dispose()
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Terminal kunne ikke åbnes')
      }
    }

    let cleanup: void | (() => void)
    open().then(fn => { cleanup = fn })

    return () => {
      cancelled = true
      if (typeof cleanup === 'function') cleanup()
      ws?.close()
      term?.dispose()
    }
  }, [deviceId])

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-gray-950 rounded-lg border border-gray-700 shadow-2xl w-full max-w-5xl h-[72vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800 flex-shrink-0">
          <div>
            <p className="text-sm text-gray-200 font-mono">{deviceId}</p>
            <p className="text-[11px] text-gray-500">
              {session
                ? `port ${session.remote_port} · ${session.identity_key_path} · udløber ${new Date(session.expires_at).toLocaleTimeString('da-DK')}`
                : 'Starter kontrolleret terminalsession...'}
            </p>
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white rounded hover:bg-gray-800">
            <X className="w-4 h-4" />
          </button>
        </div>
        {error ? (
          <div className="flex-1 flex items-center justify-center px-6 text-center">
            <p className="text-sm text-red-300">{error}</p>
          </div>
        ) : (
          <div ref={containerRef} className="flex-1 p-2 min-h-0" />
        )}
      </div>
    </div>
  )
}
