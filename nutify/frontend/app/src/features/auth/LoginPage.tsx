/**
 * Loginpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { getOidcConfig, login } from '../../lib/api/auth'
import type { OidcConfig } from '../../lib/api/auth'

const SETUP_LOGO_SRC = `${import.meta.env.BASE_URL}Nutify-Logo.png`

export function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [oidc, setOidc] = useState<OidcConfig | null>(null)

  useEffect(() => {
    let active = true
    void getOidcConfig().then((config) => {
      if (active) {
        setOidc(config)
      }
    })
    return () => {
      active = false
    }
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPending(true)
    setError(null)

    try {
      await login(username, password)
      navigate('/', { replace: true })
      window.location.href = '/'
    } catch (submitError: unknown) {
      const message = submitError instanceof Error ? submitError.message : 'Login failed'
      setError(message)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="setup-container">
      <div className="setup-header">
        <img src={SETUP_LOGO_SRC} alt="Nutify Logo" className="setup-logo" />
        <h1 className="setup-title">Nutify Login</h1>
        <div className="setup-intro">
          <p>UPS Monitoring System</p>
        </div>
      </div>

      <div className="setup-card">
        <div className="card-heading">
          <i className="fas fa-sign-in-alt" />
          <h2>User Authentication</h2>
        </div>
        <div className="card-content">
          {error ? (
            <div className="alert alert-error">
              <i className="fas fa-exclamation-triangle" /> {error}
            </div>
          ) : null}

          <form className="wizard-form" onSubmit={(event) => void handleSubmit(event)}>
            <div className="form-group">
              <label htmlFor="username">
                <i className="fas fa-user" /> Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                placeholder="Enter your username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">
                <i className="fas fa-lock" /> Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            <div className="wizard-actions">
              <button type="submit" className="nav-btn next-btn" disabled={pending}>
                <i className={`fas ${pending ? 'fa-spinner fa-spin' : 'fa-sign-in-alt'}`} />
                {pending ? 'Logging in...' : 'Login'}
              </button>
            </div>
          </form>

          {oidc?.enabled ? (
            <div className="wizard-actions">
              <a className="nav-btn prev-btn" href={oidc.login_url}>
                <i className="fas fa-right-to-bracket" /> {oidc.button_label}
              </a>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
