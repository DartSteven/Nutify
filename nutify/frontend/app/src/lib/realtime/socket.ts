/**
 * Socket.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect } from 'react'
import { io, type Socket } from 'socket.io-client'

export type RealtimeSnapshot = {
  timestamp: number
  ups_realpower?: number
  ups_load?: number
  battery_charge?: number
  battery_runtime?: number
  ups_status?: string
}

type RealtimeHandlers = {
  onSnapshot: (snapshot: RealtimeSnapshot) => void
}

let socketRef: Socket | null = null

function normalizeSnapshot(payload: unknown): RealtimeSnapshot | null {
  if (!payload || typeof payload !== 'object') {
    return null
  }

  const raw = (payload as Record<string, unknown>).data
  const data = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : (payload as Record<string, unknown>)

  const timestampValue = data.timestamp ?? data.timestamp_utc
  const parsedTimestamp = typeof timestampValue === 'number' ? timestampValue : Date.parse(String(timestampValue ?? ''))

  const snapshot: RealtimeSnapshot = {
    timestamp: Number.isFinite(parsedTimestamp) ? parsedTimestamp : Date.now(),
  }

  const keys: Array<keyof RealtimeSnapshot> = [
    'ups_realpower',
    'ups_load',
    'battery_charge',
    'battery_runtime',
    'ups_status',
  ]

  for (const key of keys) {
    const value = data[key as string]
    if (value === undefined || value === null) {
      continue
    }

    if (key === 'ups_status') {
      snapshot.ups_status = String(value)
      continue
    }

    const numeric = Number(value)
    if (Number.isFinite(numeric)) {
      snapshot[key] = numeric
    }
  }

  return snapshot
}

function getSocket(): Socket {
  if (socketRef) {
    return socketRef
  }

  socketRef = io({
    withCredentials: true,
    transports: ['websocket', 'polling'],
  })

  return socketRef
}

export function useRealtimeSocket({ onSnapshot }: RealtimeHandlers) {
  useEffect(() => {
    const socket = getSocket()

    const handleCacheUpdate = (payload: unknown) => {
      const snapshot = normalizeSnapshot(payload)
      if (snapshot) {
        onSnapshot(snapshot)
      }
    }

    const handleMultiTargetUpdate = (payload: unknown) => {
      const snapshot = normalizeSnapshot(payload)
      if (snapshot) {
        onSnapshot(snapshot)
      }
    }

    socket.on('cache_update', handleCacheUpdate)
    socket.on('multi_target_update', handleMultiTargetUpdate)

    return () => {
      socket.off('cache_update', handleCacheUpdate)
      socket.off('multi_target_update', handleMultiTargetUpdate)
    }
  }, [onSnapshot])
}
