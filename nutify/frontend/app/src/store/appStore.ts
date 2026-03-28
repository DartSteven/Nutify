/**
 * Appstore.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { create } from 'zustand'

import type { BootstrapPayload } from '../types/bootstrap'
import type { MultiNutTarget } from '../lib/api/multiNut'

type AppState = {
  bootstrap: BootstrapPayload | null
  activeTargetId: number | null
  targets: MultiNutTarget[]
  setBootstrap: (payload: BootstrapPayload) => void
  setTargets: (targets: MultiNutTarget[]) => void
  setActiveTargetId: (targetId: number | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  bootstrap: null,
  activeTargetId: null,
  targets: [],
  setBootstrap: (bootstrap) =>
    set(() => {
      const bootstrapActiveTargetId = bootstrap.monitoring.active_target_id
      const activeTargetPayload =
        bootstrap.monitoring.active_target && typeof bootstrap.monitoring.active_target === 'object'
          ? (bootstrap.monitoring.active_target as Record<string, unknown>)
          : null
      const fallbackFromPayload =
        activeTargetPayload && Number.isFinite(Number(activeTargetPayload.id))
          ? Number(activeTargetPayload['id'])
          : null

      return {
        bootstrap,
        activeTargetId: Number.isFinite(Number(bootstrapActiveTargetId))
          ? Number(bootstrapActiveTargetId)
          : fallbackFromPayload,
      }
    }),
  setTargets: (targets) => set(() => ({ targets })),
  setActiveTargetId: (targetId) => set(() => ({ activeTargetId: targetId })),
}))
