/**
 * Shared chart theme helpers.
 *
 * Canvas charts cannot use CSS variables directly, so colors are resolved from
 * the active document theme before they are passed to Chart.js/ApexCharts.
 */

export type ChartTheme = {
  mode: 'light' | 'dark'
  textColor: string
  mutedTextColor: string
  gridColor: string
  tooltipBackground: string
  tooltipTextColor: string
}

export type ChartJsThemeTarget = {
  options?: {
    plugins?: {
      legend?: { labels?: { color?: string } }
      tooltip?: { backgroundColor?: string; titleColor?: string; bodyColor?: string }
    }
    scales?: Record<
      string,
      {
        ticks?: { color?: string }
        title?: { color?: string }
        grid?: { color?: string }
      }
    >
  }
  update?: (mode?: string) => void
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function readCssVar(style: CSSStyleDeclaration, name: string, fallback: string): string {
  const value = style.getPropertyValue(name).trim()
  return value || fallback
}

function containsCssVar(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some((item) => containsCssVar(item))
  }
  return typeof value === 'string' && value.includes('var(')
}

export function resolveChartTheme(): ChartTheme {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return {
      mode: 'dark',
      textColor: '#e6edf7',
      mutedTextColor: '#b8c1d7',
      gridColor: 'rgba(255, 255, 255, 0.08)',
      tooltipBackground: 'rgba(15, 23, 42, 0.92)',
      tooltipTextColor: '#ffffff',
    }
  }

  const root = document.documentElement
  const mode = root.getAttribute('data-theme') === 'light' ? 'light' : 'dark'
  const style = window.getComputedStyle(root)

  if (mode === 'light') {
    return {
      mode,
      textColor: readCssVar(style, '--text-primary', '#0f172a'),
      mutedTextColor: readCssVar(style, '--text-secondary', '#475569'),
      gridColor: 'rgba(15, 23, 42, 0.12)',
      tooltipBackground: 'rgba(255, 255, 255, 0.96)',
      tooltipTextColor: readCssVar(style, '--text-primary', '#0f172a'),
    }
  }

  return {
    mode,
    textColor: readCssVar(style, '--text-primary', '#e6edf7'),
    mutedTextColor: readCssVar(style, '--text-secondary', '#b8c1d7'),
    gridColor: 'rgba(255, 255, 255, 0.08)',
    tooltipBackground: 'rgba(15, 23, 42, 0.92)',
    tooltipTextColor: '#ffffff',
  }
}

export function watchChartTheme(callback: () => void): () => void {
  if (typeof MutationObserver === 'undefined' || typeof document === 'undefined') {
    return () => {}
  }

  const observer = new MutationObserver(callback)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-ui-skin', 'class', 'style'],
  })
  return () => observer.disconnect()
}

export function mergeApexThemeOptions(options: Record<string, unknown>): Record<string, unknown> {
  const theme = resolveChartTheme()
  const chartConfig = isRecord(options.chart) ? options.chart : {}
  const tooltipConfig = isRecord(options.tooltip) ? options.tooltip : {}
  const gridConfig = isRecord(options.grid) ? options.grid : {}
  const legendConfig = isRecord(options.legend) ? options.legend : {}
  const legendLabels = isRecord(legendConfig.labels) ? legendConfig.labels : {}

  const explicitForeColor = chartConfig.foreColor
  const foreColor = explicitForeColor && !containsCssVar(explicitForeColor) ? explicitForeColor : theme.textColor
  const explicitLegendColors = legendLabels.colors
  const legendColors =
    explicitLegendColors && !containsCssVar(explicitLegendColors) ? explicitLegendColors : [theme.textColor]

  return {
    ...options,
    chart: {
      ...chartConfig,
      foreColor,
    },
    tooltip: {
      theme: theme.mode,
      ...tooltipConfig,
    },
    grid: {
      borderColor: theme.gridColor,
      ...gridConfig,
    },
    legend: {
      ...legendConfig,
      labels: {
        ...legendLabels,
        colors: legendColors,
      },
    },
  }
}

export function applyChartJsTheme(
  chart: unknown,
  options: { preserveTickColors?: string[]; preserveTitleColors?: string[] } = {},
): void {
  const target = chart as ChartJsThemeTarget
  const theme = resolveChartTheme()
  const preserveTickColors = new Set(options.preserveTickColors ?? [])
  const preserveTitleColors = new Set(options.preserveTitleColors ?? [])

  const legendLabels = target.options?.plugins?.legend?.labels
  if (legendLabels) {
    legendLabels.color = theme.textColor
  }

  const tooltip = target.options?.plugins?.tooltip
  if (tooltip) {
    tooltip.backgroundColor = theme.tooltipBackground
    tooltip.titleColor = theme.tooltipTextColor
    tooltip.bodyColor = theme.tooltipTextColor
  }

  Object.entries(target.options?.scales ?? {}).forEach(([scaleId, scale]) => {
    if (scale.grid) {
      scale.grid.color = theme.gridColor
    }
    if (scale.ticks && !preserveTickColors.has(scaleId)) {
      scale.ticks.color = theme.mutedTextColor
    }
    if (scale.title && !preserveTitleColors.has(scaleId)) {
      scale.title.color = theme.textColor
    }
  })

  target.update?.('none')
}
