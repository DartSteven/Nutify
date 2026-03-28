/**
 * Energydetailmodal.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { LegacyApexChart } from '../../components/LegacyApexChart'
import type { EnergySeriesPoint } from './energyPageSupport'

type EnergyDetailModalProps = {
  open: boolean
  title: string
  loading: boolean
  series: EnergySeriesPoint[]
  options: Record<string, unknown>
  onClose: () => void
}

export function EnergyDetailModal({
  open,
  title,
  loading,
  series,
  options,
  onClose,
}: EnergyDetailModalProps) {
  return (
    <div
      id="detailModal"
      className="modal_bar"
      style={{ display: open ? 'flex' : 'none' }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="modal_bar-content">
        <span className="modal_bar-close" onClick={onClose} role="button" tabIndex={0}>
          <i className="fas fa-times" aria-hidden="true" />
        </span>
        <div className="modal_bar-header">
          <div className="modal_bar-title-group">
            <h3 className="modal_bar-title">Interval Details</h3>
            <span className="modal_bar-date">{title}</span>
          </div>
        </div>
        <div id="detailChartContainer" className="modal_bar-chart">
          {open && loading ? (
            <div className="empty-state">Loading interval details...</div>
          ) : null}
          {open && !loading && series.length === 0 ? (
            <div className="empty-state">No detailed data available for the selected interval.</div>
          ) : null}
          {open && !loading && series.length > 0 ? (
            <LegacyApexChart
              options={options}
              series={[{ name: 'Detailed Cost', data: series }]}
              style={{ height: '100%', width: '100%' }}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
