// ═══════════════════════════════════════════════════════════════
// useWebRTC.ts
// WebRTC Live View hook for LAB mode (F-013)
// Version: 1.0.0 | 13. juli 2026
// ───────────────────────────────────────────────────────────────
// Bruger native RTCPeerConnection API (ingen ekstern dependency)
// ═══════════════════════════════════════════════════════════════

import { useEffect, useRef, useState, useCallback } from 'react'
import { getApiUrl, pathSegment } from '../api/client'

export interface WebRTCState {
  connected: boolean
  connecting: boolean
  error: string | null
  enabled: boolean
}

export interface UseWebRTCOptions {
  deviceId: string
  enabled: boolean
  onConnected?: () => void
  onError?: (error: string) => void
  onDisconnected?: () => void
}

const ICE_SERVERS = {
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
}

/**
 * WebRTC hook til LAB mode Live View.
 * Håndterer WebRTC peer connection og signaling via headend.
 *
 * Flow:
 * 1. Browser opretter RTCPeerConnection (initiator=true)
 * 2. Browser genererer SDP offer
 * 3. Offer sendes til headend (/api/lab/{id}/webrtc-offer)
 * 4. Edge henter offer via config polling
 * 5. Edge sender answer til headend (/api/lab/{id}/webrtc-answer)
 * 6. Browser henter answer fra headend (/api/lab/{id}/webrtc-answer)
 * 7. WebRTC forbindelse etableres
 * 8. Video stream modtages fra edge
 */
export function useWebRTC({
  deviceId,
  enabled,
  onConnected,
  onError,
  onDisconnected
}: UseWebRTCOptions) {
  const [state, setState] = useState<WebRTCState>({
    connected: false,
    connecting: false,
    error: null,
    enabled
  })

  const pcRef = useRef<RTCPeerConnection | null>(null)
  const videoTrackRef = useRef<MediaStreamTrack | null>(null)
  const retryTimerRef = useRef<number | null>(null)
  const mountedRef = useRef(true)

  // Ryd timers ved cleanup
  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  // Cleanup WebRTC connection
  const cleanup = useCallback(() => {
    clearRetryTimer()

    if (videoTrackRef.current) {
      videoTrackRef.current.stop()
      videoTrackRef.current = null
    }

    if (pcRef.current) {
      pcRef.current.close()
      pcRef.current = null
    }

    if (mountedRef.current) {
      setState(prev => ({
        ...prev,
        connected: false,
        connecting: false,
        error: null
      }))
    }

    onDisconnected?.()
  }, [clearRetryTimer, onDisconnected])

  // Opret WebRTC connection
  const connect = useCallback(async () => {
    if (!enabled || !mountedRef.current) return

    clearRetryTimer()
    setState(prev => ({ ...prev, connecting: true, error: null }))

    try {
      const apiUrl = getApiUrl()

      // 1. Opret RTCPeerConnection
      const pc = new RTCPeerConnection(ICE_SERVERS)
      pcRef.current = pc

      // 2. Håndter ICE candidates
      const iceCandidates: RTCIceCandidateInit[] = []

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          iceCandidates.push(event.candidate)
        }
      }

      pc.onconnectionstatechange = () => {
        if (!mountedRef.current) return

        const newState = pc.connectionState
        console.log('[WebRTC] Connection state:', newState)

        if (newState === 'connected') {
          setState(prev => ({ ...prev, connected: true, connecting: false, error: null }))
          onConnected?.()
        } else if (newState === 'failed' || newState === 'disconnected') {
          setState(prev => ({ ...prev, connected: false, connecting: false, error: `Connection ${newState}` }))
          onError?.(`Connection ${newState}`)

          // Retry efter 5 sekunder
          if (mountedRef.current && enabled) {
            retryTimerRef.current = window.setTimeout(() => {
              if (mountedRef.current && enabled) {
                connect()
              }
            }, 5000)
          }
        }
      }

      // 3. Håndter indkomende media tracks
      pc.ontrack = (event) => {
        console.log('[WebRTC] Received track:', event.track.kind)
        if (event.track.kind === 'video') {
          videoTrackRef.current = event.track
        }
      }

      // 4. Opret offer (browser er initiator)
      const offer = await pc.createOffer({
        offerToReceiveAudio: false,
        offerToReceiveVideo: true
      })

      await pc.setLocalDescription(offer)

      // 5. Vent på ICE gathering completion
      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === 'complete') {
          resolve()
        } else {
          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === 'complete') {
              resolve()
            }
          }
        }
      })

      // 6. Send offer til headend
      const offerResponse = await fetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/webrtc-offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ sdp: pc.localDescription?.sdp })
      })

      if (!offerResponse.ok) {
        throw new Error(`Offer failed: ${offerResponse.status}`)
      }

      console.log('[WebRTC] Offer sent, waiting for answer...')

      // 7. Poll for answer fra headend (edge skal nå at processe offer)
      let answerSdp: string | null = null
      for (let attempt = 0; attempt < 30; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 1000))

        const answerResponse = await fetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/webrtc-answer`, {
          credentials: 'include'
        })

        if (answerResponse.ok) {
          const data = await answerResponse.json()
          answerSdp = data.answer
          break
        }
      }

      if (!answerSdp) {
        throw new Error('Timeout waiting for answer - er WebRTC server kørende på edge?')
      }

      // 8. Set remote description (answer)
      await pc.setRemoteDescription(new RTCSessionDescription({
        type: 'answer',
        sdp: answerSdp
      }))

      console.log('[WebRTC] Connection established')

    } catch (err) {
      if (!mountedRef.current) return

      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      console.error('[WebRTC] Connection error:', err)

      setState(prev => ({
        ...prev,
        connected: false,
        connecting: false,
        error: errorMsg
      }))

      onError?.(errorMsg)

      // Retry efter 10 sekunder ved fejl
      if (mountedRef.current && enabled) {
        retryTimerRef.current = window.setTimeout(() => {
          if (mountedRef.current && enabled) {
            connect()
          }
        }, 10000)
      }
    }
  }, [deviceId, enabled, onConnected, onError, onDisconnected, clearRetryTimer])

  // Auto-connect når enabled ændres
  useEffect(() => {
    mountedRef.current = true

    if (enabled) {
      connect()
    } else {
      cleanup()
    }

    return () => {
      mountedRef.current = false
      cleanup()
    }
  }, [enabled])

  // Returner video stream til <video> element
  const getStream = useCallback(() => {
    if (videoTrackRef.current) {
      return new MediaStream([videoTrackRef.current])
    }
    return null
  }, [])

  return {
    ...state,
    getStream,
    reconnect: connect,
    disconnect: cleanup
  }
}
