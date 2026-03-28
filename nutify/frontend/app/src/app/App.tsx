/**
 * App.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useState } from 'react'

import { getBootstrap } from '../lib/api/bootstrap'
import { useAppStore } from '../store/appStore'
import { AppProviders } from './providers/AppProviders'
import { AppRouter } from './router/AppRouter'

export function App() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const setBootstrap = useAppStore((state) => state.setBootstrap)

  useEffect(() => {
    let mounted = true

    void getBootstrap(`${window.location.pathname}${window.location.search}`)
      .then((payload) => {
        if (!mounted) {
          return
        }

        setBootstrap(payload)
        setLoading(false)
      })
      .catch((bootstrapError: unknown) => {
        if (!mounted) {
          return
        }

        const message = bootstrapError instanceof Error ? bootstrapError.message : 'Could not bootstrap frontend'
        setError(message)
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [setBootstrap])

  if (loading) {
    return <div className="loading-screen">Loading Nutify React UI...</div>
  }

  if (error) {
    return (
      <div className="loading-screen">
        <div>
          <p className="text-xl font-semibold">Bootstrap failed</p>
          <p className="mt-2 text-sm text-slate-400">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  )
}
