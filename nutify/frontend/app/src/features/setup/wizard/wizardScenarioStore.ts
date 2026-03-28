/**
 * Wizardscenariostore.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { create } from 'zustand'

export type WizardScenarioKey =
  | null
  | 'SingleMonitorStandalone'
  | 'SingleMonitorNetworkServer'
  | 'SingleMonitorNetworkClient'
  | 'MultiMonitorRemoteNUTOnly'
  | 'MultiMonitorLocalTargetsOnlyStandalone'
  | 'MultiMonitorLocalTargetsOnlyNetworkServer'
  | 'MultiMonitorMixedLocalRemoteStandalone'
  | 'MultiMonitorMixedLocalRemoteNetworkServer'

type WizardSelection = {
  profile: 'single' | 'multi'
  mode: string | null
  topology: string | null
  hostServiceMode: 'standalone' | 'netserver'
}

type WizardScenarioState = WizardSelection & {
  scenarioKey: WizardScenarioKey
  setSelection: (selection: Partial<WizardSelection>) => void
  reset: () => void
}

const DEFAULT_SELECTION: WizardSelection = {
  profile: 'single',
  mode: null,
  topology: null,
  hostServiceMode: 'standalone',
}

export function resolveWizardScenarioKey(selection: WizardSelection): WizardScenarioKey {
  if (selection.profile === 'single') {
    switch (selection.mode) {
      case 'standalone':
        return 'SingleMonitorStandalone'
      case 'netserver':
        return 'SingleMonitorNetworkServer'
      case 'netclient':
        return 'SingleMonitorNetworkClient'
      default:
        return null
    }
  }

  switch (selection.topology) {
    case 'remote_only':
      return 'MultiMonitorRemoteNUTOnly'
    case 'local_only':
      return selection.hostServiceMode === 'netserver'
        ? 'MultiMonitorLocalTargetsOnlyNetworkServer'
        : 'MultiMonitorLocalTargetsOnlyStandalone'
    case 'mixed':
      return selection.hostServiceMode === 'netserver'
        ? 'MultiMonitorMixedLocalRemoteNetworkServer'
        : 'MultiMonitorMixedLocalRemoteStandalone'
    default:
      return null
  }
}

export const useWizardScenarioStore = create<WizardScenarioState>((set, get) => ({
  ...DEFAULT_SELECTION,
  scenarioKey: null,
  setSelection: (selection) =>
    set(() => {
      const nextSelection: WizardSelection = {
        profile: selection.profile ?? get().profile,
        mode: selection.mode ?? get().mode,
        topology: selection.topology ?? get().topology,
        hostServiceMode: selection.hostServiceMode ?? get().hostServiceMode,
      }
      return {
        ...nextSelection,
        scenarioKey: resolveWizardScenarioKey(nextSelection),
      }
    }),
  reset: () =>
    set(() => ({
      ...DEFAULT_SELECTION,
      scenarioKey: resolveWizardScenarioKey(DEFAULT_SELECTION),
    })),
}))

export function syncWizardScenarioSelection(selection: Partial<WizardSelection>) {
  useWizardScenarioStore.getState().setSelection(selection)
}
