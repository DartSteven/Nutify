/**
 * Cachewebsocketmanager.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useRef } from 'react'
import { io, type Socket } from 'socket.io-client'

type CachePayload = Record<string, unknown>

type WebSocketStateEvent = {
  connected: boolean
  reconnecting: boolean
  reconnectAttempt?: number
  maxReconnectAttempts?: number
  maxAttemptsReached?: boolean
  error?: string
}

type CacheWebSocketOptions = {
  onUpdate: (data: CachePayload) => void
  onConnect?: () => void
  onDisconnect?: () => void
  debug?: boolean
  enabled?: boolean
  acceptTargetedUpdates?: boolean
  monitoringProfile: string
  activeTargetId: number | null
}

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY_MS = 5000

function normalizePayload(payload: unknown): CachePayload {
  if (!payload || typeof payload !== 'object') {
    return {}
  }

  const source = payload as Record<string, unknown>
  const raw = source.data && typeof source.data === 'object' ? (source.data as Record<string, unknown>) : source
  const metrics = raw.metrics && typeof raw.metrics === 'object' ? (raw.metrics as Record<string, unknown>) : null

  return metrics ? { ...raw, ...metrics } : raw
}

function extractMetricsFromTargetPayload(payload: unknown): CachePayload {
  const empty: CachePayload = {}
  if (!payload || typeof payload !== 'object') {
    return empty
  }

  const root = payload as Record<string, unknown>
  const data = root.data && typeof root.data === 'object' ? (root.data as Record<string, unknown>) : empty
  const latest = data.latest && typeof data.latest === 'object' ? (data.latest as Record<string, unknown>) : empty
  const metrics: CachePayload = {}

  const jsonValue = latest.data_json
  if (typeof jsonValue === 'string' && jsonValue.trim().length > 0) {
    try {
      const parsed = JSON.parse(jsonValue)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        Object.assign(metrics, parsed as CachePayload)
      }
    } catch {
      // Keep fallback flat fields below when JSON payload is malformed.
    }
  }

  for (const key of ['ups_status', 'battery_charge', 'battery_runtime', 'ups_load', 'ups_realpower', 'input_voltage']) {
    const value = latest[key]
    if (value !== undefined) {
      metrics[key] = value
    }
  }

  return metrics
}

export function useCacheWebSocketManager({
  onUpdate,
  onConnect,
  onDisconnect,
  debug = false,
  enabled = true,
  acceptTargetedUpdates = false,
  monitoringProfile,
  activeTargetId,
}: CacheWebSocketOptions) {
  const onUpdateRef = useRef(onUpdate)
  const onConnectRef = useRef(onConnect)
  const onDisconnectRef = useRef(onDisconnect)

  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  useEffect(() => {
    onConnectRef.current = onConnect
  }, [onConnect])

  useEffect(() => {
    onDisconnectRef.current = onDisconnect
  }, [onDisconnect])

  useEffect(() => {
    if (!enabled) {
      return
    }

    let reconnectInterval: number | null = null
    let reconnectAttempts = 0
    let isUnmounted = false

    const socket: Socket = io({
      withCredentials: true,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
    })

    const log = (message: string, error = false) => {
      if (!debug && !error) {
        return
      }
      if (error) {
        console.error(`[CacheWebSocket] ${message}`)
        return
      }
      console.debug(`[CacheWebSocket] ${message}`)
    }

    const normalizedProfile = String(monitoringProfile || 'single').trim().toLowerCase()
    const supportsTargetScopedRealtime = normalizedProfile === 'single' || normalizedProfile === 'multi'
    const resolvedActiveTargetId = Number(activeTargetId)
    const hasActiveTargetOverride = () =>
      supportsTargetScopedRealtime && Number.isFinite(resolvedActiveTargetId) && resolvedActiveTargetId > 0

    const dispatchStateEvent = (state: WebSocketStateEvent) => {
      window.dispatchEvent(new CustomEvent('websocket_state', { detail: state }))
    }

    const dispatchMessageEvent = (data: CachePayload) => {
      window.dispatchEvent(new CustomEvent('websocket_message', { detail: data }))
    }

    const fetchActiveTargetSnapshotOnce = async () => {
      if (!hasActiveTargetOverride() || isUnmounted) {
        return
      }

      try {
        const response = await fetch(`/api/multi-nut/targets/${resolvedActiveTargetId}`, {
          credentials: 'same-origin',
        })
        if (!response.ok) {
          return
        }

        const payload = (await response.json()) as unknown
        const metrics = extractMetricsFromTargetPayload(payload)
        onUpdateRef.current(metrics)
        dispatchMessageEvent(metrics)
      } catch (error) {
        log(`Error loading initial active target snapshot: ${String(error)}`)
      }
    }

    const setupReconnection = () => {
      if (reconnectInterval || isUnmounted) {
        return
      }

      reconnectAttempts += 1
      dispatchStateEvent({
        connected: false,
        reconnecting: true,
        reconnectAttempt: reconnectAttempts,
        maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
      })

      if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
        dispatchStateEvent({
          connected: false,
          reconnecting: false,
          maxAttemptsReached: true,
        })
        log('Max reconnect attempts reached', true)
        return
      }

      reconnectInterval = window.setInterval(() => {
        if (!socket.connected && !isUnmounted) {
          log('Attempting to reconnect WebSocket...')
          socket.connect()
        }
      }, RECONNECT_DELAY_MS)
    }

    const clearReconnectInterval = () => {
      if (reconnectInterval) {
        window.clearInterval(reconnectInterval)
        reconnectInterval = null
      }
    }

    const handleConnect = () => {
      reconnectAttempts = 0
      clearReconnectInterval()
      socket.emit('request_cache_data')
      if (hasActiveTargetOverride()) {
        void fetchActiveTargetSnapshotOnce()
      }
      onConnectRef.current?.()
      dispatchStateEvent({ connected: true, reconnecting: false })
      log('WebSocket connected')
    }

    const handleDisconnect = () => {
      onDisconnectRef.current?.()
      dispatchStateEvent({ connected: false, reconnecting: false })
      setupReconnection()
      log('WebSocket disconnected')
    }

    const handleConnectError = (error: Error) => {
      onDisconnectRef.current?.()
      dispatchStateEvent({
        connected: false,
        reconnecting: false,
        error: error.message || 'Connection error',
      })
      setupReconnection()
      log(`WebSocket connection error: ${error.message}`, true)
    }

    const handleCacheUpdate = (payload: unknown) => {
      const source = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null

      if (hasActiveTargetOverride()) {
        const incomingTargetId = Number(source?.target_id ?? source?.targetId)
        if (!Number.isFinite(incomingTargetId) || incomingTargetId !== resolvedActiveTargetId) {
          return
        }
        const normalized = normalizePayload(payload)
        onUpdateRef.current(normalized)
        dispatchMessageEvent(normalized)
        return
      }

      if (
        !acceptTargetedUpdates &&
        source &&
        (source.target_id !== undefined || source.targetId !== undefined)
      ) {
        // Ignore targeted multi-updates when no specific target is selected in the main dashboard.
        return
      }

      const normalized = normalizePayload(payload)
      onUpdateRef.current(normalized)
      dispatchMessageEvent(normalized)
    }

    socket.on('connect', handleConnect)
    socket.on('disconnect', handleDisconnect)
    socket.on('connect_error', handleConnectError)
    socket.on('cache_update', handleCacheUpdate)
    socket.on('multi_target_update', handleCacheUpdate)

    if (socket.connected) {
      handleConnect()
    } else {
      socket.connect()
    }

    return () => {
      isUnmounted = true
      clearReconnectInterval()
      socket.off('connect', handleConnect)
      socket.off('disconnect', handleDisconnect)
      socket.off('connect_error', handleConnectError)
      socket.off('cache_update', handleCacheUpdate)
      socket.off('multi_target_update', handleCacheUpdate)
      socket.disconnect()
    }
  }, [acceptTargetedUpdates, activeTargetId, debug, enabled, monitoringProfile])
}
