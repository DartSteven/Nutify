const NETWORK_DRIVER_MARKERS = ['snmp', 'netxml', 'ipmi']

export function isNetworkUpsDriver(driverValue: unknown): boolean {
  const normalized = String(driverValue || '').trim().toLowerCase()
  return NETWORK_DRIVER_MARKERS.some((marker) => normalized.includes(marker))
}

export function updateDriverEndpointPresentation(
  driverValue: unknown,
  endpointInput: HTMLInputElement | null,
  labelElement: HTMLElement | null,
  helpElement: HTMLElement | null,
): void {
  if (!endpointInput) return

  const usesNetworkEndpoint = isNetworkUpsDriver(driverValue)
  if (labelElement) {
    labelElement.textContent = usesNetworkEndpoint ? 'UPS Host/IP:' : 'Port/Device:'
  }
  if (helpElement) {
    helpElement.textContent = usesNetworkEndpoint
      ? 'Required: hostname or IP address of the UPS network management interface. Do not use auto.'
      : 'Use auto for USB, or enter the local device path required by the selected driver.'
  }

  endpointInput.placeholder = usesNetworkEndpoint ? 'ups.example.net or 192.168.1.238' : 'auto or /dev/ttyS0'
  const currentValue = String(endpointInput.value || '').trim()
  if (usesNetworkEndpoint && currentValue.toLowerCase() === 'auto') {
    endpointInput.value = ''
  } else if (!usesNetworkEndpoint && !currentValue) {
    endpointInput.value = 'auto'
  }
}
