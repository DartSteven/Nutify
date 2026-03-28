/**
 * Databasesection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getDatabaseBackupDownloadUrl,
  getDatabaseStats,
  getVariableConfig,
  optimizeDatabase,
  vacuumDatabase,
} from '../../../lib/api/settings'
import { useAppStore } from '../../../store/appStore'

type TableStat = {
  name: string
  recordCount: number
  lastWrite: string | null
}

type DatabaseStats = {
  size: number
  totalRecords: number
  lastWrite: string | null
  tables: TableStat[]
}

type AlertState = {
  tone: 'success' | 'danger'
  text: string
} | null

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 Bytes'
  }

  const units = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = 0

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }

  return `${value.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`
}

function formatDate(value: string | null, timezone: string): string {
  if (!value) {
    return 'Never'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  try {
    return parsed.toLocaleString(undefined, { timeZone: timezone })
  } catch {
    return parsed.toLocaleString()
  }
}

function normalizeStats(payload: unknown): DatabaseStats {
  if (!payload || typeof payload !== 'object') {
    return { size: 0, totalRecords: 0, lastWrite: null, tables: [] }
  }

  const data = (payload as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    return { size: 0, totalRecords: 0, lastWrite: null, tables: [] }
  }

  const row = data as Record<string, unknown>
  const tableRows: TableStat[] = []
  const tables = row.tables

  if (tables && typeof tables === 'object') {
    Object.entries(tables as Record<string, unknown>).forEach(([name, value]) => {
      if (!value || typeof value !== 'object') {
        return
      }
      const table = value as Record<string, unknown>
      tableRows.push({
        name,
        recordCount: Number(table.record_count ?? 0),
        lastWrite: table.last_write ? String(table.last_write) : null,
      })
    })
  }

  tableRows.sort((left, right) => left.name.localeCompare(right.name))

  return {
    size: Number(row.size ?? 0),
    totalRecords: Number(row.total_records ?? 0),
    lastWrite: row.last_write ? String(row.last_write) : null,
    tables: tableRows,
  }
}

function ActionCard(props: {
  icon: string
  title: string
  description: string
  buttonId: string
  alertId: string
  buttonText: string
  buttonIcon: string
  alert: AlertState
  pending: boolean
  onClick: () => void
}) {
  const { icon, title, description, buttonId, alertId, buttonText, buttonIcon, alert, pending, onClick } =
    props
  return (
    <div className="stat_card">
      <div className="stat-icon">
        <i className={`fas ${icon}`} />
      </div>
      <div className="stat-content">
        <div className="stat-label">{title}</div>
        <p className="stat-description">{description}</p>
        <button
          type="button"
          id={buttonId}
          className="database_action_btn"
          onClick={onClick}
          disabled={pending}
        >
          <i className={`fas ${buttonIcon}`} /> {pending ? 'Working...' : buttonText}
        </button>
        <div id={alertId} className={`options_alert ${alert ? '' : 'hidden'}`}>
          {alert ? alert.text : ''}
        </div>
      </div>
    </div>
  )
}

export function DatabaseSection() {
  const queryClient = useQueryClient()
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const bootstrapTimezone = useAppStore((state) => state.bootstrap?.timezone ?? 'UTC')
  const [optimizeAlert, setOptimizeAlert] = useState<AlertState>(null)
  const [vacuumAlert, setVacuumAlert] = useState<AlertState>(null)

  const variableConfigQuery = useQuery({
    queryKey: ['settings', 'database', 'variable-config', activeTargetId],
    queryFn: () => getVariableConfig(activeTargetId),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const timezone = useMemo(() => {
    const scopedTimezone = String(variableConfigQuery.data?.timezone ?? '').trim()
    return scopedTimezone || bootstrapTimezone
  }, [bootstrapTimezone, variableConfigQuery.data?.timezone])

  const statsQuery = useQuery({
    queryKey: ['settings', 'database', 'stats'],
    queryFn: getDatabaseStats,
    refetchInterval: 15000,
  })

  const stats = useMemo(() => normalizeStats(statsQuery.data), [statsQuery.data])

  const optimizeMutation = useMutation({
    mutationFn: optimizeDatabase,
    onSuccess: async () => {
      setOptimizeAlert({ tone: 'success', text: 'Database optimized successfully.' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'database', 'stats'] })
    },
    onError: (error: unknown) => {
      const text = error instanceof Error ? error.message : 'Error optimizing database'
      setOptimizeAlert({ tone: 'danger', text })
    },
  })

  const vacuumMutation = useMutation({
    mutationFn: vacuumDatabase,
    onSuccess: async () => {
      setVacuumAlert({ tone: 'success', text: 'Database vacuumed successfully.' })
      await queryClient.invalidateQueries({ queryKey: ['settings', 'database', 'stats'] })
    },
    onError: (error: unknown) => {
      const text = error instanceof Error ? error.message : 'Error vacuuming database'
      setVacuumAlert({ tone: 'danger', text })
    },
  })

  return (
    <div className="combined_card">
      <div className="card_header">
        <h2>Database Status</h2>
        <p className="card_subtitle">
          Monitor and manage your database (snapshots, profiles and rollups included).
        </p>
      </div>

      <div className="stats_grid">
        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-database" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Database Size</div>
            <div className="stat-value" id="dbSize">
              {formatBytes(stats.size)}
            </div>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-database" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Total Records</div>
            <div className="stat-value" id="totalRecords">
              {stats.totalRecords.toLocaleString()}
            </div>
          </div>
        </div>

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-database" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Last Write</div>
            <div
              className="stat-value"
              id="lastWrite"
              style={{ fontSize: '0.9rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}
            >
              {formatDate(stats.lastWrite, timezone)}
            </div>
          </div>
        </div>
      </div>

      <div className="stats_grid">
        <ActionCard
          icon="fa-bug-slash"
          title="Optimize Database"
          description="Analyzes and reorganizes the database indexes to improve query performance."
          buttonId="optimizeDbBtn"
          alertId="databaseStatusOptimize"
          buttonText="Optimize Database"
          buttonIcon="fa-wrench"
          alert={optimizeAlert}
          pending={optimizeMutation.isPending}
          onClick={() => optimizeMutation.mutate()}
        />

        <ActionCard
          icon="fa-compress-arrows-alt"
          title="Vacuum Database"
          description="Removes unused space and defragments the database, reducing its physical size."
          buttonId="vacuumDbBtn"
          alertId="databaseStatusVaccum"
          buttonText="Vacuum Database"
          buttonIcon="fa-broom"
          alert={vacuumAlert}
          pending={vacuumMutation.isPending}
          onClick={() => vacuumMutation.mutate()}
        />

        <div className="stat_card">
          <div className="stat-icon">
            <i className="fas fa-download" />
          </div>
          <div className="stat-content">
            <div className="stat-label">Download Backup</div>
            <p className="stat-description">Download the latest backup of the database.</p>
            <button
              type="button"
              id="backupDbBtn"
              className="database_action_btn"
              onClick={() => {
                window.location.href = getDatabaseBackupDownloadUrl()
              }}
            >
              <i className="fas fa-cloud-download-alt" /> Download Backup
            </button>
          </div>
        </div>
      </div>

      <div className="tables_grid">
        <h3>Tables Information</h3>
        <div id="tablesInfo" className="grid_container">
          {stats.tables.map((table) => (
            <div className="table_info_card" key={table.name}>
              <div className="table_info_header">
                <i className="fas fa-table" />
                <h4>{table.name}</h4>
              </div>
              <div className="table_info_stats">
                <div className="table_info_stat">
                  <div className="table_info_stat_label">Records</div>
                  <div className="table_info_stat_value">{table.recordCount.toLocaleString()}</div>
                </div>
                <div className="table_info_stat">
                  <div className="table_info_stat_label">Last Write</div>
                  <div className="table_info_stat_value">{formatDate(table.lastWrite, timezone)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
