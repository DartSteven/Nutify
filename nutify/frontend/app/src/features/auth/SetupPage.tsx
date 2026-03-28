/**
 * Setuppage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { setupAdmin } from '../../lib/api/auth'

export function SetupPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setPending(true)
    setError(null)

    try {
      await setupAdmin(username, password, confirmPassword)
      navigate('/auth/login', { replace: true })
      window.location.href = '/auth/login'
    } catch (setupError: unknown) {
      const message = setupError instanceof Error ? setupError.message : 'Setup failed'
      setError(message)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-100">Initial Admin Setup</h1>
        <p className="mt-2 text-sm text-slate-400">Create the first dashboard account for Nutify.</p>
      </div>

      <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
        <label className="field-group">
          <span className="field-label">Username</span>
          <input className="input-base" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>

        <label className="field-group">
          <span className="field-label">Password</span>
          <input
            className="input-base"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        <label className="field-group">
          <span className="field-label">Confirm password</span>
          <input
            className="input-base"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </label>

        {error ? <p className="text-sm text-rose-300">{error}</p> : null}

        <button className="btn-primary w-full" type="submit" disabled={pending}>
          {pending ? 'Creating account...' : 'Create account'}
        </button>
      </form>
    </div>
  )
}
