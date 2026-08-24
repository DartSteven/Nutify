/**
 * Multiupslocationnetworkchart.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'

import {
  GLOBE_DISTANCE_MAX,
  GLOBE_DISTANCE_MIN,
  type LocationPoint,
  type RenderMode,
  asChartPoints,
  build2dMapOption,
  buildGlobeOption,
  clamp,
  computeViewControl,
  ensureGlobeTexturesReady,
  ensureLocalWorldMapRegistered,
  hasWebGlSupport,
} from './MultiUpsLocationNetworkChart.options'

type Props = {
  points: LocationPoint[]
}

export function MultiUpsLocationNetworkChart({ points }: Props) {
  const [renderMode, setRenderMode] = useState<RenderMode>('none')
  const [globeDistanceOverride, setGlobeDistanceOverride] = useState<number | null>(null)
  const [geoZoomOverride, setGeoZoomOverride] = useState<number | null>(null)
  const [resetNonce, setResetNonce] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function initMode() {
      if (hasWebGlSupport()) {
        const globeAssetsReady = await ensureGlobeTexturesReady()
        if (globeAssetsReady) {
          if (!cancelled) {
            setRenderMode('globe')
          }
          return
        }
      }

      const hasWorldMap = await ensureLocalWorldMapRegistered()
      if (!cancelled) {
        setRenderMode(hasWorldMap ? 'map' : 'none')
      }
    }

    void initMode()

    return () => {
      cancelled = true
    }
  }, [])

  const chartPoints = useMemo(() => asChartPoints(points), [points])
  const coordinateSignature = useMemo(
    () =>
      chartPoints
        .map((point) => {
          const [longitude, latitude] = point.coordinates
          return [point.id, point.isPrimary ? '1' : '0', longitude.toFixed(5), latitude.toFixed(5)].join(':')
        })
        .join('|'),
    [chartPoints],
  )
  const viewControl = useMemo(() => {
    if (chartPoints.length === 0) {
      return null
    }
    return computeViewControl(chartPoints)
  }, [chartPoints])

  useEffect(() => {
    setGlobeDistanceOverride(null)
    setGeoZoomOverride(null)
    setResetNonce((previous) => previous + 1)
  }, [coordinateSignature, renderMode])

  const effectiveViewControl = useMemo(() => {
    if (!viewControl) {
      return null
    }
    return {
      ...viewControl,
      distance: globeDistanceOverride ?? viewControl.distance,
      geoZoom: geoZoomOverride ?? viewControl.geoZoom,
    }
  }, [viewControl, globeDistanceOverride, geoZoomOverride])

  const chartOption = useMemo(() => {
    if (chartPoints.length === 0 || !effectiveViewControl) {
      return null
    }
    if (renderMode === 'globe') {
      return buildGlobeOption(chartPoints, effectiveViewControl)
    }
    if (renderMode === 'map') {
      return build2dMapOption(chartPoints, effectiveViewControl)
    }
    return null
  }, [renderMode, chartPoints, effectiveViewControl])

  const applyZoomStep = useCallback(
    (direction: 'in' | 'out') => {
      if (!viewControl) {
        return
      }
      if (renderMode === 'globe') {
        setGlobeDistanceOverride((previous) => {
          const baseDistance = previous ?? viewControl.distance
          const delta = direction === 'in' ? -8 : 8
          return clamp(baseDistance + delta, GLOBE_DISTANCE_MIN, GLOBE_DISTANCE_MAX)
        })
        return
      }

      if (renderMode === 'map') {
        setGeoZoomOverride((previous) => {
          const baseZoom = previous ?? viewControl.geoZoom
          const nextZoom = baseZoom * (direction === 'in' ? 1.28 : 0.78)
          return clamp(nextZoom, 1, 14)
        })
      }
    },
    [renderMode, viewControl],
  )

  const resetView = useCallback(() => {
    setGlobeDistanceOverride(null)
    setGeoZoomOverride(null)
    setResetNonce((previous) => previous + 1)
  }, [])

  if (points.length === 0) {
    return <p className="card_subtitle">No targets with location data available.</p>
  }

  if (!viewControl) {
    return (
      <p className="card_subtitle">
        No validated coordinates found for the current targets. Re-save wizard locations to populate latitude/longitude.
      </p>
    )
  }

  if (!chartOption) {
    return <p className="card_subtitle">Unable to render world map assets for the network graph.</p>
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '.45rem', marginBottom: '.45rem' }}>
        <button
          type="button"
          className="options_btn options_btn_secondary options_btn_small"
          onClick={() => applyZoomStep('in')}
          aria-label="Zoom in network graph"
        >
          +
        </button>
        <button
          type="button"
          className="options_btn options_btn_secondary options_btn_small"
          onClick={() => applyZoomStep('out')}
          aria-label="Zoom out network graph"
        >
          -
        </button>
        <button
          type="button"
          className="options_btn options_btn_secondary options_btn_small"
          onClick={resetView}
          aria-label="Reset network graph view"
        >
          Reset
        </button>
      </div>
      <ReactECharts
        key={`${renderMode}-${resetNonce}`}
        option={chartOption}
        style={{ height: 500, width: '100%' }}
        notMerge={false}
        lazyUpdate
        opts={{ renderer: 'canvas' }}
      />
      {renderMode === 'map' ? (
        <p className="card_subtitle">
          WebGL unavailable in this browser/runtime. Showing 2D world map fallback (no axes) with the same UPS flow.
        </p>
      ) : null}
    </div>
  )
}
