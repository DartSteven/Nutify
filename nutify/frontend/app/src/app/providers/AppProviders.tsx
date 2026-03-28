/**
 * Appproviders.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

type AppProvidersProps = {
  children: ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
