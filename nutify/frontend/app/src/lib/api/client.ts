/**
 * Client.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { z } from 'zod'

export class ApiError extends Error {
  public readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

const frontendEnvelopeSchema = z.object({
  success: z.boolean().optional(),
  data: z.unknown().optional(),
  error: z.string().optional(),
  message: z.string().optional(),
})

type RequestOptions = RequestInit & {
  signal?: AbortSignal
}

export async function requestJson<T>(url: string, schema: z.ZodType<T>, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  const text = await response.text()
  const json = text ? JSON.parse(text) : {}

  if (!response.ok) {
    const parsed = frontendEnvelopeSchema.safeParse(json)
    const errorMessage = parsed.success
      ? parsed.data.error ?? parsed.data.message ?? `HTTP ${response.status}`
      : `HTTP ${response.status}`
    throw new ApiError(errorMessage, response.status)
  }

  const parsed = schema.safeParse(json)
  if (!parsed.success) {
    throw new ApiError(`Invalid API payload for ${url}`, 500)
  }

  return parsed.data
}

export function buildTargetQuery(targetId: number | null): string {
  if (!targetId) {
    return ''
  }
  return `target_id=${targetId}`
}

export function withTarget(url: string, targetId: number | null): string {
  if (!targetId) {
    return url
  }

  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}${buildTargetQuery(targetId)}`
}
