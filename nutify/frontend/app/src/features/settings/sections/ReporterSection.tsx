/**
 * Reportersection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo } from 'react'

import { useAppStore } from '../../../store/appStore'
import { MailSection } from './MailSection'

type ReporterSectionProps = {
  title?: string
  subtitle?: string
}

export function ReporterSection({
  title = 'Reporter Routing',
  subtitle,
}: ReporterSectionProps = {}) {
  const activeTargetId = useAppStore((state) => state.activeTargetId)
  const targets = useAppStore((state) => state.targets)

  const activeTargetName = useMemo(() => {
    const selected = targets.find((target) => Number(target.id) === Number(activeTargetId))
    if (selected?.name) {
      return selected.name
    }
    if (Number.isFinite(Number(activeTargetId)) && Number(activeTargetId) > 0) {
      return `Target #${activeTargetId}`
    }
    return 'active UPS target'
  }, [activeTargetId, targets])

  const resolvedSubtitle =
    subtitle || `Configure report delivery for ${activeTargetName}. Report delivery currently uses configured email providers.`

  return (
    <>
      <div className="options_card">
        <div className="card_header">
          <div className="notification_header">
            <h2>{title}</h2>
          </div>
          <p className="card_subtitle">{resolvedSubtitle}</p>
        </div>
      </div>

      <MailSection showConfigPanel={false} showNotificationsPanel={false} />
    </>
  )
}
