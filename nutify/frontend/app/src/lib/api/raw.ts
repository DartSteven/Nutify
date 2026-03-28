/**
 * Raw.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { withTarget } from './client'

export async function fetchRawJson(url: string, targetId: number | null): Promise<unknown> {
  const response = await fetch(withTarget(url, targetId), {
    credentials: 'same-origin',
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} on ${url}`)
  }

  return response.json()
}
