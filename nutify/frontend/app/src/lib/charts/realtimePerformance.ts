export const REALTIME_FRAME_RATE = 24

const MIN_REFRESH_MS = 1_000
const MAX_REFRESH_MS = 10_000
const MAX_DEVICE_PIXEL_RATIO = 1.5

export function resolveRealtimeRefreshMs(pollingIntervalMs: number): number {
  const interval = Number(pollingIntervalMs)
  if (!Number.isFinite(interval) || interval <= 0) {
    return MIN_REFRESH_MS
  }
  return Math.max(MIN_REFRESH_MS, Math.min(MAX_REFRESH_MS, Math.round(interval)))
}

export function resolveRealtimeDelayMs(refreshMs: number): number {
  return Math.max(250, Math.min(1_000, Math.round(refreshMs)))
}

export function resolveChartPixelRatio(): number {
  const ratio = Number(window.devicePixelRatio)
  if (!Number.isFinite(ratio) || ratio <= 0) {
    return 1
  }
  return Math.min(ratio, MAX_DEVICE_PIXEL_RATIO)
}

export function pauseRealtimeWhenHidden(): boolean {
  return document.hidden
}
