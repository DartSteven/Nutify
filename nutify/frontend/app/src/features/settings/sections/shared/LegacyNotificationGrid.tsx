/**
 * Legacynotificationgrid.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { LEGACY_NOTIFICATION_EVENTS } from './notificationEvents'

export type LegacyNotificationSelection = {
  enabled: boolean
  configId: string
}

type ConfigOption = {
  value: string
  label: string
}

type LegacyNotificationGridProps = {
  prefix: string
  selectClassName: string
  checkboxClassName: string
  testClassName: string
  emptyOptionLabel: string
  configOptions: ConfigOption[]
  selections: Record<string, LegacyNotificationSelection>
  testBusyEventType: string | null
  onConfigChange: (eventType: string, configId: string) => void
  onEnabledChange: (eventType: string, enabled: boolean) => void
  onTest: (eventType: string) => void
}

export function LegacyNotificationGrid(props: LegacyNotificationGridProps) {
  const {
    prefix,
    selectClassName,
    checkboxClassName,
    testClassName,
    emptyOptionLabel,
    configOptions,
    selections,
    testBusyEventType,
    onConfigChange,
    onEnabledChange,
    onTest,
  } = props

  return (
    <div className="options_nutify_grid">
      {LEGACY_NOTIFICATION_EVENTS.map((eventMeta) => {
        const state = selections[eventMeta.eventType] ?? { enabled: false, configId: '' }
        const hasSelection = Boolean(state.configId)
        const inputId = `${prefix}_${eventMeta.inputIdSuffix}`
        const isTesting = testBusyEventType === eventMeta.eventType

        return (
          <div className="options_notification_card" key={eventMeta.eventType}>
            <div className="options_nutify_header">
              <div className="options_nutify_icon">
                <i className={`fas ${eventMeta.iconClass}`} />
              </div>
              <div className="options_nutify_title_container">
                <span className="options_nutify_title">{eventMeta.title}</span>
                <span className="options_nutify_description">{eventMeta.description}</span>
              </div>
              <button
                type="button"
                className={`options_btn ${testClassName}`}
                data-event-type={eventMeta.eventType}
                style={{ display: hasSelection ? 'inline-block' : 'none' }}
                onClick={() => onTest(eventMeta.eventType)}
              >
                <span className="btn-text" style={{ display: isTesting ? 'none' : 'inline' }}>
                  Test
                </span>
                <span className={`btn-loader ${isTesting ? '' : 'hidden'}`}>
                  <i className="fas fa-spinner fa-spin" />
                </span>
              </button>
              <div className="options_nutify_toggle">
                <div className="toggle-switch">
                  <input
                    type="checkbox"
                    id={inputId}
                    className={`${checkboxClassName} toggle-input`}
                    data-event-type={eventMeta.eventType}
                    style={{ display: hasSelection ? 'inline-block' : 'none' }}
                    checked={hasSelection ? state.enabled : false}
                    onChange={(event) => onEnabledChange(eventMeta.eventType, event.target.checked)}
                  />
                  <label htmlFor={inputId} className="toggle-label">
                    <span className="toggle-inner" />
                    <span className="toggle-switch-text-on">ON</span>
                    <span className="toggle-switch-text-off">OFF</span>
                  </label>
                </div>
              </div>
            </div>
            <div className="options_nutify_body">
              <select
                className={selectClassName}
                data-event-type={eventMeta.eventType}
                value={state.configId}
                onChange={(event) => onConfigChange(eventMeta.eventType, event.target.value)}
              >
                <option value="">{emptyOptionLabel}</option>
                {configOptions.map((option) => (
                  <option key={`${eventMeta.eventType}-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )
      })}
    </div>
  )
}
