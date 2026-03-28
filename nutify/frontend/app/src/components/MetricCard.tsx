/**
 * Metriccard.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { ReactNode } from 'react'

type MetricRow = {
  label: string
  value: string
  stacked?: boolean
}

type MetricCardProps = {
  title: string
  value: string
  icon?: string
  detail?: string
  periodLabel?: string
  rows?: MetricRow[]
  trend?: ReactNode
}

const EMPTY_CARD_VALUES = new Set([
  '',
  '--',
  '-',
  'n/a',
  'na',
  'unknown',
  'unknow',
  'null',
  'undefined',
  'none',
  'not available',
])

function normalizeValue(value: string | undefined): string {
  return String(value ?? '').trim().toLowerCase()
}

function isMeaningfulValue(value: string | undefined): boolean {
  const normalized = normalizeValue(value)
  if (!normalized) {
    return false
  }
  if (EMPTY_CARD_VALUES.has(normalized)) {
    return false
  }

  const compact = normalized.replace(/\s+/g, '')
  if (compact === 'n/a/n/a' || compact === 'n/a|n/a') {
    return false
  }

  if (/^0+(?:\.0+)?(?:\s*(%|w|kw|v|min|mins|minute|minutes|s|sec|secs|second|seconds|wh|kwh|ah|mah|°c|c|f))?$/.test(normalized)) {
    return false
  }

  if (/^min\s*0+(?:\.0+)?\s*[a-z%°]*\s*\|\s*max\s*0+(?:\.0+)?\s*[a-z%°]*$/.test(normalized)) {
    return false
  }

  return true
}

export function MetricCard({ title, value, icon, detail, periodLabel = 'Now', rows, trend }: MetricCardProps) {
  const visibleRows = Array.isArray(rows) ? rows.filter((row) => isMeaningfulValue(row.value)) : []
  const hasRows = visibleRows.length > 0
  const hasMainValue = isMeaningfulValue(value)
  const hasDetail = isMeaningfulValue(detail)

  if (!hasMainValue && !hasRows && !hasDetail && !trend) {
    return null
  }

  return (
    <article className="stat_card">
      {icon ? (
        <div className="stat-icon">
          <i className={`fas ${icon}`} aria-hidden="true" />
        </div>
      ) : null}
      <div className="stat-content">
        <div className="stat-header">
          <span className="stat-label">{title}</span>
          <span className="selected-period">{periodLabel}</span>
        </div>
        {!hasRows ? <span className="stat-value">{value}</span> : null}
        {hasDetail && detail ? <span className="stat-detail">{detail}</span> : null}
        {hasRows ? (
          <div className="stat-rows">
            {visibleRows.map((row) => (
              <div
                key={`${row.label}:${row.value}`}
                className={['stat-row', row.stacked ? 'stat-row--stacked' : ''].join(' ').trim()}
              >
                <span className="stat-row-label">{row.label}</span>
                <span className="stat-row-value">{row.value}</span>
              </div>
            ))}
          </div>
        ) : null}
        {trend ? <div className="stat-trend">{trend}</div> : null}
      </div>
    </article>
  )
}
