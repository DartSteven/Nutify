/**
 * Wizardstepconfiguration.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo } from 'react'
import { MultiMonitorLocalTargetsOnlyNetworkServer } from './scenarios/MultiMonitorLocalTargetsOnlyNetworkServer'
import { MultiMonitorLocalTargetsOnlyStandalone } from './scenarios/MultiMonitorLocalTargetsOnlyStandalone'
import { MultiMonitorMixedLocalRemoteNetworkServer } from './scenarios/MultiMonitorMixedLocalRemoteNetworkServer'
import { MultiMonitorMixedLocalRemoteStandalone } from './scenarios/MultiMonitorMixedLocalRemoteStandalone'
import { MultiMonitorRemoteNUTOnly } from './scenarios/MultiMonitorRemoteNUTOnly'
import { SingleMonitorNetworkClient } from './scenarios/SingleMonitorNetworkClient'
import { SingleMonitorNetworkServer } from './scenarios/SingleMonitorNetworkServer'
import { SingleMonitorStandalone } from './scenarios/SingleMonitorStandalone'
import { useWizardScenarioStore } from './wizardScenarioStore'

export function WizardStepConfiguration() {
  const scenarioKey = useWizardScenarioStore((state) => state.scenarioKey)

  const activeMultiScenario = useMemo(() => {
    switch (scenarioKey) {
      case 'MultiMonitorRemoteNUTOnly':
        return <MultiMonitorRemoteNUTOnly />
      case 'MultiMonitorLocalTargetsOnlyStandalone':
        return <MultiMonitorLocalTargetsOnlyStandalone />
      case 'MultiMonitorLocalTargetsOnlyNetworkServer':
        return <MultiMonitorLocalTargetsOnlyNetworkServer />
      case 'MultiMonitorMixedLocalRemoteStandalone':
        return <MultiMonitorMixedLocalRemoteStandalone />
      case 'MultiMonitorMixedLocalRemoteNetworkServer':
        return <MultiMonitorMixedLocalRemoteNetworkServer />
      default:
        return null
    }
  }, [scenarioKey])

  return (
    <div className="wizard-step-content hidden" id="step-4">
      <SingleMonitorStandalone />
      <SingleMonitorNetworkServer />
      <SingleMonitorNetworkClient />
      <div id="primary-target-workflow" className="hidden" style={{ marginTop: '16px' }}>
        <button
          type="button"
          id="primary-target-test-save-btn"
          className="nav-btn next-btn hidden"
          style={{ display: 'none' }}
        >
          <i className="fas fa-check-circle" /> Test &amp; Save Primary Target
        </button>
        <div id="primary-target-workflow-status" className="form-help hidden" />
      </div>
      {activeMultiScenario}
    </div>
  )
}
