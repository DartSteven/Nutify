/**
 * Notificationevents.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type NotificationEventMeta = {
  eventType: string
  inputIdSuffix: string
  iconClass: string
  title: string
  description: string
}

export const LEGACY_NOTIFICATION_EVENTS: NotificationEventMeta[] = [
  {
    eventType: 'ONLINE',
    inputIdSuffix: 'online',
    iconClass: 'fa-plug',
    title: 'UPS on Line Power',
    description: 'Notify when UPS returns to line power',
  },
  {
    eventType: 'ONBATT',
    inputIdSuffix: 'onbatt',
    iconClass: 'fa-battery-half',
    title: 'UPS on Battery',
    description: 'Notify when UPS switches to battery power',
  },
  {
    eventType: 'LOWBATT',
    inputIdSuffix: 'lowbatt',
    iconClass: 'fa-battery-empty',
    title: 'Low Battery',
    description: 'Notify when battery is running low',
  },
  {
    eventType: 'COMMOK',
    inputIdSuffix: 'commok',
    iconClass: 'fa-wifi',
    title: 'Communication Restored',
    description: 'Notify when UPS communication is restored',
  },
  {
    eventType: 'COMMBAD',
    inputIdSuffix: 'commbad',
    iconClass: 'fa-times-circle',
    title: 'Communication Lost',
    description: 'Notify when UPS communication is lost',
  },
  {
    eventType: 'SHUTDOWN',
    inputIdSuffix: 'shutdown',
    iconClass: 'fa-power-off',
    title: 'Shutdown Imminent',
    description: 'Notify when system shutdown is about to start',
  },
  {
    eventType: 'REPLBATT',
    inputIdSuffix: 'replbatt',
    iconClass: 'fa-battery-full',
    title: 'Replace Battery',
    description: 'Notify when battery needs replacement',
  },
  {
    eventType: 'NOCOMM',
    inputIdSuffix: 'nocomm',
    iconClass: 'fa-wifi-slash',
    title: 'No Communication',
    description: 'Notify when UPS is not reachable',
  },
  {
    eventType: 'NOPARENT',
    inputIdSuffix: 'noparent',
    iconClass: 'fa-child',
    title: 'Parent Process Lost',
    description: 'Notify when parent process is lost',
  },
]
