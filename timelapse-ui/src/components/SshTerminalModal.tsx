import { useEffect, useRef, useState } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { X } from 'lucide-react'
import { startAuthentication } from '@simplewebauthn/browser'
import { useAbortPasskeyOnLeave, withPasskeyDeadline } from '../lib/passkey'
import { getApiUrl } from '../api/client'

const RESIZE_PREFIX = '\x01RESIZE:'

interface TerminalSession {
  session_id: string
  websocket_path: string
  expires_at?: string
  host_fingerprint?: string
  identity_key_path?: string
  remote_port?: number
  target?: string
  login?: 'passkey' | 'password'
}

// deviceId HEADEND_CONSOLE = the Headend itself, via its admin SSH (password + TOTP)
export const HEADEND_CONSOLE = '__headend__'

async function postJson(url: string, body?: unknown) {
  return fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

// Headend console: fresh passkey (Touch ID / Windows Hello) → SSO login.
// Without SSO installed or without a passkey it falls back to password + TOTP.
async function headendAssertion(): Promise<unknown | null> {
  const res = await postJson(`${getApiUrl()}/api/admin/headend-console/stepup/begin`)
  if (!res.ok) return null
  const begin = await res.json()
  if (!begin.available) return null
  try {
    return await withPasskeyDeadline(startAuthentication({ optionsJSON: begin.options }))
  } catch {
    return null   // passkey dialog cancelled → password + TOTP instead
  }
}

async function startTerminalSession(deviceId: string): Promise<TerminalSession> {
  let res: Response
  if (deviceId === HEADEND_CONSOLE) {
    const assertion = await headendAssertion()
    res = await postJson(`${getApiUrl()}/api/admin/headend-console/sessions`, assertion ? { assertion } : {})
  } else {
    res = await postJson(`${getApiUrl()}/api/admin/ssh-tunnel/${encodeURIComponent(deviceId)}/terminal-sessions`)
  }
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
  useAbortPasskeyOnLeave()
  const containerRef = useRef<HTMLDivElement>(null)
  const backdropPress = useRef(false)
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
          term?.write(deviceId === HEADEND_CONSOLE
            ? (created.login === 'passkey'
                ? `\x1b[36mForbinder til Headend via admin-SSH (${created.target ?? '127.0.0.1:9122'}) — logget ind med passkey\x1b[0m\r\n`
                : `\x1b[36mForbinder til Headend via admin-SSH (${created.target ?? '127.0.0.1:9122'}) — log ind med adgangskode og TOTP-kode\x1b[0m\r\n`)
            : `\x1b[36mForbinder til ${deviceId} via verified reverse tunnel...\x1b[0m\r\n`)
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
    // Close only when BOTH press and release happen on the backdrop. Selecting
    // text in the terminal and releasing outside the window fires a click on
    // the backdrop (common ancestor) and used to close the terminal.
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
      onMouseDown={e => { backdropPress.current = e.target === e.currentTarget }}
      onClick={e => { if (backdropPress.current && e.target === e.currentTarget) onClose(); backdropPress.current = false }}
    >
      <div
        className="bg-gray-950 rounded-lg border border-gray-700 shadow-2xl w-full max-w-5xl h-[72vh] flex flex-col overflow-hidden"
      >
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800 flex-shrink-0">
          <div>
            <p className="text-sm text-gray-200 font-mono">{deviceId === HEADEND_CONSOLE ? 'Headend (denne server)' : deviceId}</p>
            <p className="text-[11px] text-gray-500">
              {session
                ? (deviceId === HEADEND_CONSOLE
                    ? `${session.target} · ${session.login === 'passkey' ? 'passkey (SSO)' : 'adgangskode + TOTP'} · maks. 30 min`
                    : `port ${session.remote_port} · ${session.identity_key_path} · udløber ${session.expires_at ? new Date(session.expires_at).toLocaleTimeString('da-DK') : '–'}`)
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
          // Padding on the wrapper, not on the element xterm measures: FitAddon
          // sizes rows from its parent's height, and border-box padding made it
          // count ~16 px that are not there (bottom row cut in half).
          <div className="flex-1 p-2 min-h-0 overflow-hidden">
            <div ref={containerRef} className="h-full w-full" />
          </div>
        )}
      </div>
    </div>
  )
}
