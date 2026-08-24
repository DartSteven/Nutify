/**
 * Loginpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { forgotPassword, getOidcConfig, login } from '../../lib/api/auth'
import type { OidcConfig } from '../../lib/api/auth'
import './loginAuthentication.css'

const SETUP_LOGO_SRC = `${import.meta.env.BASE_URL}Nutify-Logo.png`
const LOCAL_LOGIN_VALUES = new Set(['1', 'true', 'yes', 'on'])

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forceLocalLogin = LOCAL_LOGIN_VALUES.has((searchParams.get('local') ?? '').trim().toLowerCase())
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [showRecovery, setShowRecovery] = useState(false)
  const [recoveryUsername, setRecoveryUsername] = useState('')
  const [recoveryKey, setRecoveryKey] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [recoveryPending, setRecoveryPending] = useState(false)
  const [recoveryStatus, setRecoveryStatus] = useState<string | null>(null)
  const [oidc, setOidc] = useState<OidcConfig | null>(null)
  const [oidcLoaded, setOidcLoaded] = useState(false)
  const [loginMethod, setLoginMethod] = useState<'local' | null>(forceLocalLogin ? 'local' : null)

  useEffect(() => {
    let active = true
    void getOidcConfig().then((config) => {
      if (active) {
        setOidc(config)
        setOidcLoaded(true)
      }
    })
    return () => {
      active = false
    }
  }, [])

  const autoRedirecting = Boolean(oidc?.enabled && oidc.auto_redirect && !forceLocalLogin)

  useEffect(() => {
    if (autoRedirecting && oidc) window.location.replace(oidc.login_url)
  }, [autoRedirecting, oidc])

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

  const handleRecoverySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setRecoveryPending(true)
    setRecoveryStatus(null)

    try {
      await forgotPassword(recoveryUsername, newPassword, confirmPassword, recoveryKey)
      setRecoveryStatus('Password reset successful. Login with new password.')
      setRecoveryKey('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (submitError: unknown) {
      const message = submitError instanceof Error ? submitError.message : 'Password reset failed'
      setRecoveryStatus(message)
    } finally {
      setRecoveryPending(false)
    }
  }

  if (autoRedirecting && oidc) {
    return (
      <div className="setup-container login-authentication-page">
        <div className="setup-header">
          <img src={SETUP_LOGO_SRC} alt="Nutify Logo" className="setup-logo" />
          <h1 className="setup-title">Nutify Login</h1>
        </div>
        <div className="setup-card">
          <div className="card-heading">
            <i className="fas fa-right-to-bracket" />
            <h2>Signing you in</h2>
          </div>
          <div className="card-content">
            <p>Redirecting to {oidc.provider_name}...</p>
            <div className="wizard-actions">
              <a className="nav-btn next-btn" href={oidc.login_url}>{oidc.button_label}</a>
              <a className="nav-btn prev-btn" href="/auth/login?local=1">Use local login</a>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!oidcLoaded) {
    return (
      <div className="setup-container login-authentication-page">
        <div className="setup-header"><img src={SETUP_LOGO_SRC} alt="Nutify Logo" className="setup-logo" /><h1 className="setup-title">Nutify Login</h1></div>
        <div className="setup-card"><div className="card-content"><p><i className="fas fa-spinner fa-spin" /> Loading sign-in methods...</p></div></div>
      </div>
    )
  }

  if (oidc?.enabled && !forceLocalLogin && loginMethod === null) {
    return (
      <div className="setup-container login-authentication-page">
        <div className="setup-header">
          <img src={SETUP_LOGO_SRC} alt="Nutify Logo" className="setup-logo" />
          <h1 className="setup-title">Nutify Login</h1>
          <div className="setup-intro"><p>Choose how you want to sign in</p></div>
        </div>
        <div className="setup-card">
          <div className="card-heading"><i className="fas fa-shield-halved" /><h2>Secure access</h2></div>
          <div className="card-content login-methods">
            <a className="login-method login-method-sso" href={oidc.login_url}>
              <span className="login-method-icon"><i className="fas fa-fingerprint" /></span>
              <span className="login-method-copy"><strong>{oidc.button_label}</strong><small>Continue securely through {oidc.provider_name}.</small><em>Recommended</em></span>
            </a>
            <button type="button" className="login-method" onClick={() => setLoginMethod('local')}>
              <span className="login-method-icon"><i className="fas fa-user-lock" /></span>
              <span className="login-method-copy"><strong>Sign in with Nutify account</strong><small>Use your local Nutify username and password.</small><em>Local access</em></span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="setup-container login-authentication-page">
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
          {oidc?.enabled && !forceLocalLogin ? (
            <button type="button" className="login-method-back" onClick={() => setLoginMethod(null)}>
              <i className="fas fa-arrow-left" /> Back to sign-in methods
            </button>
          ) : null}
          {error ? (
            <div className="alert alert-error">
              <i className="fas fa-exclamation-triangle" /> {error}
            </div>
          ) : null}

          {oidc?.configuration_error ? (
            <div className="alert alert-error">
              <i className="fas fa-triangle-exclamation" /> SSO configuration is invalid. Local login remains available.
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
            <div className="wizard-actions" style={{ justifyContent: 'center' }}>
              <button
                type="button"
                className="nav-btn prev-btn"
                onClick={() => {
                  setShowRecovery((prev) => !prev)
                  setRecoveryStatus(null)
                }}
              >
                <i className="fas fa-key" />
                {showRecovery ? 'Hide Recovery' : 'Forgot Password'}
              </button>
            </div>
          </form>

          {showRecovery ? (
            <form className="wizard-form" onSubmit={(event) => void handleRecoverySubmit(event)}>
              <div className="form-group">
                <label htmlFor="recovery_username">
                  <i className="fas fa-user-shield" /> Admin Username
                </label>
                <input
                  id="recovery_username"
                  type="text"
                  value={recoveryUsername}
                  onChange={(event) => setRecoveryUsername(event.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="recovery_key">
                  <i className="fas fa-unlock-alt" /> Recovery Key (SECRET_KEY)
                </label>
                <input
                  id="recovery_key"
                  type="password"
                  value={recoveryKey}
                  onChange={(event) => setRecoveryKey(event.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="new_password_recovery">
                  <i className="fas fa-lock" /> New Password
                </label>
                <input
                  id="new_password_recovery"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="confirm_password_recovery">
                  <i className="fas fa-check-circle" /> Confirm New Password
                </label>
                <input
                  id="confirm_password_recovery"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                />
              </div>
              {recoveryStatus ? (
                <div className={`alert ${recoveryStatus.toLowerCase().includes('successful') ? 'alert-success' : 'alert-error'}`}>
                  <i className="fas fa-info-circle" /> {recoveryStatus}
                </div>
              ) : null}
              <div className="wizard-actions">
                <button type="submit" className="nav-btn next-btn" disabled={recoveryPending}>
                  <i className={`fas ${recoveryPending ? 'fa-spinner fa-spin' : 'fa-key'}`} />
                  {recoveryPending ? 'Resetting...' : 'Reset Password'}
                </button>
              </div>
            </form>
          ) : null}
        </div>
      </div>
    </div>
  )
}
