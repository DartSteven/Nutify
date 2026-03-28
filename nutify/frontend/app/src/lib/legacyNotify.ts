/**
 * Legacynotify.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

type NotificationType = 'info' | 'success' | 'error' | 'warning'

type NotifyFn = (message: string, type?: NotificationType, duration?: number | boolean) => HTMLDivElement | null

declare global {
  interface Window {
    notify?: NotifyFn
  }
}

const STYLE_ID = 'notification-styles'
const CONTAINER_ID = 'notification-container'

function normalizeDuration(duration?: number | boolean): number {
  if (typeof duration === 'boolean') {
    return 5000
  }
  if (typeof duration === 'number' && Number.isFinite(duration)) {
    return Math.max(duration, 5000)
  }
  return 5000
}

function ensureNotificationsCssLoaded(): void {
  if (document.getElementById(STYLE_ID)) {
    return
  }

  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
#${CONTAINER_ID} {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  pointer-events: none;
  max-width: 350px;
  gap: 10px;
}

.notification {
  padding: 12px 16px;
  border-radius: 6px;
  border-left: 4px solid;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  width: 100%;
  background-color: #2d3748;
  color: #e2e8f0;
  pointer-events: auto;
  position: relative;
  overflow: hidden;
  font-weight: 500;
  min-width: 300px;
  transform: translateX(100%);
  opacity: 0;
  transition: transform 0.5s ease-out, opacity 0.5s ease-out;
}

.notification-visible {
  transform: translateX(0);
  opacity: 1;
}

.notification-hidden {
  transform: translateX(100%);
  opacity: 0;
  transition: transform 0.5s ease-in, opacity 0.5s ease-in;
}

.notification-success {
  background-color: #065f46;
  color: #ecfdf5;
  border-left-color: #34d399;
}

.notification-error {
  background-color: #991b1b;
  color: #fee2e2;
  border-left-color: #f87171;
}

.notification-warning {
  background-color: #92400e;
  color: #fef3c7;
  border-left-color: #fbbf24;
}

.notification-info {
  background-color: #1e40af;
  color: #e0f2fe;
  border-left-color: #38bdf8;
}

.notification i {
  margin-right: 10px;
  font-size: 18px;
}

.notification-success i {
  color: #34d399;
}

.notification-error i {
  color: #f87171;
}

.notification-warning i {
  color: #fbbf24;
}

.notification-info i {
  color: #38bdf8;
}

:root[data-theme="dark"] .notification {
  background: #2a3444;
  color: #e2e8f0;
}

:root[data-theme="light"] .notification {
  background: #f1f5f9;
  color: #334155;
}

:root[data-theme="light"] .notification-info {
  border-left-color: #0284c7;
}

:root[data-theme="light"] .notification-info i {
  color: #0284c7;
}
`

  document.head.appendChild(style)
}

function getNotificationContainer(): HTMLElement {
  const existing = document.getElementById(CONTAINER_ID)
  if (existing) {
    return existing
  }

  const container = document.createElement('div')
  container.id = CONTAINER_ID
  document.body.appendChild(container)
  return container
}

function getIconClass(type: NotificationType): string {
  if (type === 'success') {
    return 'fa-check-circle'
  }
  if (type === 'error') {
    return 'fa-exclamation-circle'
  }
  if (type === 'warning') {
    return 'fa-exclamation-triangle'
  }
  return 'fa-info-circle'
}

function notify(message: string, type: NotificationType = 'info', duration?: number | boolean): HTMLDivElement | null {
  if (typeof document === 'undefined') {
    return null
  }

  const safeDuration = normalizeDuration(duration)
  ensureNotificationsCssLoaded()

  const notification = document.createElement('div')
  notification.className = `notification notification-${type}`
  notification.classList.add('notification-visible')
  notification.innerHTML = `<i class="fas ${getIconClass(type)}"></i><span>${message}</span>`

  const container = getNotificationContainer()
  container.insertBefore(notification, container.firstChild)

  const timer = window.setTimeout(() => {
    notification.classList.add('notification-hidden')
    window.setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification)
      }
      if (container.children.length === 0 && container.parentNode) {
        container.parentNode.removeChild(container)
      }
    }, 500)
  }, safeDuration)

  notification.addEventListener(
    'click',
    () => {
      window.clearTimeout(timer)
      notification.classList.add('notification-hidden')
      window.setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification)
        }
      }, 300)
    },
    { once: true },
  )

  return notification
}

export function initializeLegacyNotify(): void {
  if (typeof window === 'undefined') {
    return
  }
  ensureNotificationsCssLoaded()
  window.notify = notify
}

