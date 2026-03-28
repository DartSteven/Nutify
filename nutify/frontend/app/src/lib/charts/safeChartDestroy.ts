/**
 * Safechartdestroy.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

type DestroyableChart = {
  destroy: () => void
}

function isBenignChartDestroyError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    message.includes("reading 'node'") ||
    message.includes("can't access property \"node\"") ||
    message.includes('destroy') ||
    message.includes('Canvas is already in use') ||
    message.includes('Cannot read properties of null')
  )
}

export function destroyChartSafely(chart: DestroyableChart | null | undefined, label: string): void {
  if (!chart) {
    return
  }

  try {
    chart.destroy()
  } catch (error) {
    if (isBenignChartDestroyError(error)) {
      console.debug(`Skipped benign chart destroy error in ${label}`, error)
      return
    }
    console.error(`Failed to destroy chart in ${label}`, error)
  }
}
