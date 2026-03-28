/**
 * Topbar Target Sync Hook.
 *
 * Keeps target list and active target selection aligned with multi-target backend state.
 */

import { useEffect, type Dispatch, type SetStateAction } from 'react'

import { getMultiNutState, getOverview, getTargets, type MultiNutTarget } from '../lib/api/multiNut'
import { asRecord } from './topbarHelpers'

type UseTopbarTargetSyncInput = {
  activeTargetId: number | null
  monitoringProfile: string
  setTargets: (targets: MultiNutTarget[]) => void
  setActiveTargetId: (targetId: number | null) => void
  setFleetStatusByTarget: Dispatch<SetStateAction<Record<number, string>>>
}

export function useTopbarTargetSync({
  activeTargetId,
  monitoringProfile,
  setTargets,
  setActiveTargetId,
  setFleetStatusByTarget,
}: UseTopbarTargetSyncInput) {
  useEffect(() => {
    if (monitoringProfile !== 'multi') {
      return
    }

    let mounted = true
    let refreshTimer: number | null = null

    const refreshTargets = async (preserveCurrent = true) => {
      try {
        const [targetRows, state, overviewRows] = await Promise.all([
          getTargets(),
          getMultiNutState(),
          getOverview(24).catch(() => []),
        ])
        if (!mounted) {
          return
        }
        setTargets(targetRows)
        const statusPatch: Record<number, string> = {}
        if (Array.isArray(overviewRows)) {
          for (const item of overviewRows) {
            const row = asRecord(item)
            const target = asRecord(row.target)
            const targetId = Number(target.id)
            if (!Number.isFinite(targetId) || targetId <= 0) {
              continue
            }
            const latestMetrics = asRecord(row.latest_metrics)
            const summary = asRecord(row.summary)
            const statusValue =
              (latestMetrics.ups_status as string | undefined) ??
              (summary.latest_status as string | undefined) ??
              'UNKNOWN'
            statusPatch[targetId] = String(statusValue || 'UNKNOWN')
          }
        }
        if (Object.keys(statusPatch).length > 0) {
          setFleetStatusByTarget((previous) => ({ ...previous, ...statusPatch }))
        }

        const enabledTargetIds = new Set(targetRows.map((target) => target.id))
        const serverActiveTargetId = state.active_target_id ?? null
        const hasLocalActiveTarget =
          activeTargetId !== null && activeTargetId !== undefined && enabledTargetIds.has(activeTargetId)

        if (!preserveCurrent) {
          if (hasLocalActiveTarget) {
            return
          }
          if (serverActiveTargetId && enabledTargetIds.has(serverActiveTargetId)) {
            setActiveTargetId(serverActiveTargetId)
            return
          }
          if (!hasLocalActiveTarget && targetRows.length > 0) {
            setActiveTargetId(targetRows[0].id)
          }
          return
        }

        if (hasLocalActiveTarget) {
          return
        }

        if (serverActiveTargetId && enabledTargetIds.has(serverActiveTargetId)) {
          setActiveTargetId(serverActiveTargetId)
          return
        }

        if (targetRows.length > 0) {
          setActiveTargetId(targetRows[0].id)
        }
      } catch {
        // Keep current topbar state unchanged if target refresh fails.
      }
    }

    void refreshTargets(false)
    refreshTimer = window.setInterval(() => void refreshTargets(true), 15000)

    return () => {
      mounted = false
      if (refreshTimer) {
        window.clearInterval(refreshTimer)
      }
    }
  }, [activeTargetId, monitoringProfile, setActiveTargetId, setFleetStatusByTarget, setTargets])
}
