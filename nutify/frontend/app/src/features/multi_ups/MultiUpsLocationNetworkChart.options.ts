/**
 * Multiupslocationnetworkchart Options.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import * as echarts from 'echarts'
import 'echarts-gl'

export type Coordinate = [number, number]
export type RenderMode = 'globe' | 'map' | 'none'
export type TargetHealth = 'online' | 'on_battery' | 'warning' | 'critical' | 'offline'

export type LocationPoint = {
  id: number
  name: string
  location: string
  city: string
  country: string
  latitude?: number | null
  longitude?: number | null
  isPrimary: boolean
  isOnline: boolean
  health: TargetHealth
}

export type ChartPoint = LocationPoint & {
  coordinates: Coordinate
}

export type ViewControl = {
  targetCoord: Coordinate
  distance: number
  alpha: number
  geoZoom: number
}

type TooltipData = Record<string, unknown> & {
  health?: TargetHealth
  location?: unknown
}

type TooltipParams = {
  name?: unknown
  seriesType?: string
  data?: TooltipData
}

export const GLOBE_DISTANCE_MIN = 18
export const GLOBE_DISTANCE_MAX = 220

const ASSET_BASE = import.meta.env.BASE_URL || '/'

function assetUrl(path: string): string {
  const cleanedBase = ASSET_BASE.endsWith('/') ? ASSET_BASE : `${ASSET_BASE}/`
  const cleanedPath = path.startsWith('/') ? path.slice(1) : path
  return `${cleanedBase}${cleanedPath}`
}

const WORLD_MAP_LOCAL_URL = assetUrl('maps/world.json')
const WORLD_TEXTURE_URL = assetUrl('maps/textures/world.topo.bathy.200401.jpg')
const WORLD_HEIGHT_TEXTURE_URL = assetUrl('maps/textures/bathymetry_bw_composite_4k.jpg')
const WORLD_BACKGROUND_TEXTURE_URL = assetUrl('maps/textures/starfield.jpg')

const HEALTH_COLORS: Record<TargetHealth, string> = {
  online: '#37d67a',
  on_battery: '#f8d26a',
  warning: '#ff9f43',
  critical: '#ff5a70',
  offline: '#d84a5f',
}

const HEALTH_LABELS: Record<TargetHealth, string> = {
  online: 'Online',
  on_battery: 'On Battery',
  warning: 'Warning',
  critical: 'Critical',
  offline: 'Offline',
}

function escapeTooltipHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;',
    }
    return entities[character]
  })
}

function buildLinkTooltip(data: Record<string, unknown> | undefined, health: string): string {
  const fromName = escapeTooltipHtml(data?.fromName || 'Primary')
  const toName = escapeTooltipHtml(data?.toName || 'Target')
  return `${fromName} &rarr; ${toName}<br/>State: ${health}`
}

function buildNodeTooltip(params: TooltipParams, health: string): string {
  const name = escapeTooltipHtml(params.name || 'Target')
  const location = escapeTooltipHtml(String(params.data?.location || '').trim() || '-')
  return `<strong>${name}</strong><br/>State: ${health}<br/>Location: ${location}`
}

let localWorldMapRegistrationPromise: Promise<boolean> | null = null
let globeTexturesReadyPromise: Promise<boolean> | null = null

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value))
}

function coerceCoordinate(value: unknown, minimum: number, maximum: number): number | null {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }
  if (parsed < minimum || parsed > maximum) {
    return null
  }
  return parsed
}

export function hasWebGlSupport() {
  try {
    const canvas = document.createElement('canvas')
    const webglContext = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    return Boolean(webglContext)
  } catch {
    return false
  }
}

export function asChartPoints(points: LocationPoint[]): ChartPoint[] {
  return points
    .map((point) => {
      const latitude = coerceCoordinate(point.latitude, -90, 90)
      const longitude = coerceCoordinate(point.longitude, -180, 180)
      if (latitude === null || longitude === null) {
        return null
      }
      return {
        ...point,
        coordinates: [longitude, latitude] as Coordinate,
      }
    })
    .filter((point): point is ChartPoint => Boolean(point))
}

export async function ensureLocalWorldMapRegistered(): Promise<boolean> {
  const existingMap = typeof echarts.getMap === 'function' ? echarts.getMap('world') : null
  if (existingMap) {
    return true
  }

  if (!localWorldMapRegistrationPromise) {
    localWorldMapRegistrationPromise = (async () => {
      try {
        const response = await fetch(WORLD_MAP_LOCAL_URL, { cache: 'force-cache' })
        if (!response.ok) {
          return false
        }
        const geoJson = await response.json()
        echarts.registerMap('world', geoJson as Parameters<typeof echarts.registerMap>[1])
        return true
      } catch {
        return false
      }
    })()
  }

  const success = await localWorldMapRegistrationPromise
  if (!success) {
    localWorldMapRegistrationPromise = null
  }
  return success
}

async function ensureImageAsset(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const image = new Image()
    image.onload = () => resolve(true)
    image.onerror = () => resolve(false)
    image.src = url
  })
}

export async function ensureGlobeTexturesReady(): Promise<boolean> {
  if (!globeTexturesReadyPromise) {
    globeTexturesReadyPromise = Promise.all([
      ensureImageAsset(WORLD_TEXTURE_URL),
      ensureImageAsset(WORLD_HEIGHT_TEXTURE_URL),
      ensureImageAsset(WORLD_BACKGROUND_TEXTURE_URL),
    ]).then((values) => values.every(Boolean))
  }
  const ready = await globeTexturesReadyPromise
  if (!ready) {
    globeTexturesReadyPromise = null
  }
  return ready
}

export function computeViewControl(chartPoints: ChartPoint[]): ViewControl {
  const longitudes = chartPoints.map((point) => point.coordinates[0])
  const latitudes = chartPoints.map((point) => point.coordinates[1])
  const minLongitude = Math.min(...longitudes)
  const maxLongitude = Math.max(...longitudes)
  const minLatitude = Math.min(...latitudes)
  const maxLatitude = Math.max(...latitudes)

  const longitudeSpan = Math.max(8, maxLongitude - minLongitude)
  const latitudeSpan = Math.max(6, maxLatitude - minLatitude)
  const dominantSpan = Math.max(longitudeSpan, latitudeSpan)

  return {
    targetCoord: [
      clamp((minLongitude + maxLongitude) / 2, -180, 180),
      clamp((minLatitude + maxLatitude) / 2, -90, 90),
    ],
    distance: clamp(22 + dominantSpan * 0.85, 24, 130),
    alpha: clamp(80 - latitudeSpan * 0.45, 34, 82),
    geoZoom: clamp(8.6 - dominantSpan / 18, 1.4, 9.2),
  }
}

function buildSeriesData(chartPoints: ChartPoint[]) {
  const primaryPoint = chartPoints.find((point) => point.isPrimary) ?? chartPoints[0]

  const linesData = chartPoints
    .filter((point) => point.id !== primaryPoint.id)
    .map((point) => ({
      fromName: primaryPoint.name,
      toName: point.name,
      health: point.health,
      coords: [primaryPoint.coordinates, point.coordinates] as [Coordinate, Coordinate],
      lineStyle: {
        color: HEALTH_COLORS[point.health],
        width: point.health === 'critical' || point.health === 'offline' ? 2.2 : 1.6,
        opacity: point.health === 'offline' ? 0.45 : 0.82,
      },
    }))

  const nodesData = chartPoints.map((point) => ({
    name: point.name,
    value: [...point.coordinates, 0],
    location: point.location,
    health: point.health,
    symbolSize: point.health === 'critical' || point.health === 'offline' ? 16 : 14,
    itemStyle: {
      color: HEALTH_COLORS[point.health],
      borderColor: point.isPrimary ? '#f4f8ff' : 'rgba(200, 220, 255, 0.82)',
      borderWidth: point.isPrimary ? 2.1 : 1.2,
    },
  }))

  return { linesData, nodesData }
}

export function buildGlobeOption(chartPoints: ChartPoint[], viewControl: ViewControl) {
  const { linesData, nodesData } = buildSeriesData(chartPoints)

  return {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params: TooltipParams) => {
        if (params.seriesType === 'lines3D') {
          const health = HEALTH_LABELS[(params.data?.health as TargetHealth) || 'online']
          return buildLinkTooltip(params.data, health)
        }
        const health = HEALTH_LABELS[(params.data?.health as TargetHealth) || 'online']
        return buildNodeTooltip(params, health)
      },
    },
    globe: {
      baseTexture: WORLD_TEXTURE_URL,
      heightTexture: WORLD_HEIGHT_TEXTURE_URL,
      displacementScale: 0.03,
      shading: 'lambert',
      environment: WORLD_BACKGROUND_TEXTURE_URL,
      atmosphere: {
        show: true,
        color: 'rgba(100, 160, 255, 0.38)',
      },
      light: {
        ambient: {
          intensity: 0.48,
        },
        main: {
          intensity: 0.92,
          shadow: false,
        },
      },
      viewControl: {
        autoRotate: false,
        targetCoord: viewControl.targetCoord,
        distance: viewControl.distance,
        alpha: viewControl.alpha,
        minDistance: GLOBE_DISTANCE_MIN,
        maxDistance: GLOBE_DISTANCE_MAX,
      },
    },
    series: [
      {
        name: 'UPS Links',
        type: 'lines3D',
        coordinateSystem: 'globe',
        lineStyle: {
          width: 1.8,
          opacity: 0.7,
          color: '#67b1ff',
        },
        effect: {
          show: true,
          trailWidth: 1.9,
          trailLength: 0.2,
          trailOpacity: 0.9,
          constantSpeed: 16,
        },
        data: linesData,
      },
      {
        name: 'UPS Nodes',
        type: 'scatter3D',
        coordinateSystem: 'globe',
        label: {
          show: false,
          formatter: '{b}',
          position: 'right',
          color: '#e5f0ff',
          fontSize: 13,
        },
        emphasis: {
          label: {
            show: true,
            color: '#e5f0ff',
            fontSize: 13,
          },
        },
        itemStyle: {
          opacity: 1,
        },
        data: nodesData,
      },
    ],
  }
}

export function build2dMapOption(chartPoints: ChartPoint[], viewControl: ViewControl) {
  const { linesData, nodesData } = buildSeriesData(chartPoints)

  return {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params: TooltipParams) => {
        if (params.seriesType === 'lines') {
          const health = HEALTH_LABELS[(params.data?.health as TargetHealth) || 'online']
          return buildLinkTooltip(params.data, health)
        }
        const health = HEALTH_LABELS[(params.data?.health as TargetHealth) || 'online']
        return buildNodeTooltip(params, health)
      },
    },
    geo: {
      map: 'world',
      roam: true,
      center: viewControl.targetCoord,
      zoom: viewControl.geoZoom,
      itemStyle: {
        areaColor: 'rgba(20, 30, 48, 0.96)',
        borderColor: 'rgba(123, 183, 255, 0.36)',
        borderWidth: 0.9,
      },
      emphasis: {
        itemStyle: {
          areaColor: 'rgba(41, 72, 120, 0.96)',
        },
      },
      silent: false,
    },
    series: [
      {
        name: 'UPS Links',
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: 2,
        lineStyle: {
          width: 1.8,
          opacity: 0.7,
          curveness: 0.24,
          color: '#67b1ff',
        },
        effect: {
          show: true,
          period: 5.5,
          trailLength: 0.26,
          symbol: 'circle',
          symbolSize: 5.5,
        },
        data: linesData,
      },
      {
        name: 'UPS Nodes',
        type: 'effectScatter',
        coordinateSystem: 'geo',
        zlevel: 3,
        rippleEffect: {
          brushType: 'stroke',
          scale: 2.6,
        },
        label: {
          show: true,
          formatter: '{b}',
          position: 'right',
          color: '#e5f0ff',
          fontSize: 12,
        },
        data: nodesData,
      },
    ],
  }
}
