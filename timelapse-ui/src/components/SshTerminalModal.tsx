// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — SshTerminalModal.tsx
// ───────────────────────────────────────────────────────────────────────────
// 2026-08-06 (Claude, Peter): in-browser SSH terminal for Admin -> SSH
// Tunnels, mirroring the edge's own xterm.js break-glass terminal
// (edge/scripts/totp-service.py). Talks to headend/api/ssh_tunnel_terminal_api.py
// over a WebSocket — headend itself is the SSH client here, connecting
// through the already-established reverse tunnel with the shared
// timelapse_headend_ed25519 key. A leading \x01RESIZE:cols,rows text frame
// is the one control message on top of an otherwise plain bidirectional
// text stream (same minimal protocol as the edge's own terminal) — anything
// else is raw terminal data.
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { X } from 'lucide-react'
import { getApiUrl } from '../api/client'

const RESIZE_PREFIX = '\x01RESIZE:'

export function SshTerminalModal({ deviceId, onClose }: { deviceId: string; onClose: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: '"SF Mono", Menlo, Monaco, monospace',
      theme: { background: '#0a0e1a', foreground: '#e2e8f0' },
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    const apiUrl = getApiUrl()
    const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws'
    const wsHost = apiUrl.replace(/^https?:\/\//, '')
    const ws = new WebSocket(`${wsProtocol}://${wsHost}/api/admin/ssh-tunnel/${encodeURIComponent(deviceId)}/terminal`)

    const sendResize = () => {
      if (ws.readyState === WebSocket.OPEN) ws.send(`${RESIZE_PREFIX}${term.cols},${term.rows}`)
    }

    ws.onopen = () => {
      term.write(`\x1b[36mForbinder til ${deviceId} via reverse tunnel…\x1b[0m\r\n`)
      sendResize()
    }
    ws.onmessage = ev => term.write(ev.data)
    ws.onerror = () => term.write('\r\n\x1b[31m[WebSocket-fejl — se browser-konsollen]\x1b[0m\r\n')
    ws.onclose = () => term.write('\r\n\x1b[33m[Forbindelse lukket]\x1b[0m\r\n')

    const dataDisposable = term.onData(data => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data)
    })

    const handleResize = () => {
      fitAddon.fit()
      sendResize()
    }
    window.addEventListener('resize', handleResize)
    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(containerRef.current)

    return () => {
      window.removeEventListener('resize', handleResize)
      resizeObserver.disconnect()
      dataDisposable.dispose()
      ws.close()
      term.dispose()
    }
  }, [deviceId])

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-gray-950 rounded-xl border border-gray-700 shadow-2xl w-full max-w-4xl h-[70vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800 flex-shrink-0">
          <p className="text-sm text-gray-300 font-mono">{deviceId} — SSH terminal</p>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white rounded hover:bg-gray-800">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div ref={containerRef} className="flex-1 p-2 min-h-0" />
      </div>
    </div>
  )
}
