import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteOidcAdminConfig,
  discoverOidcProvider,
  getOidcAdminConfig,
  registerOidcClient,
  saveOidcAdminConfig,
  setOidcEnabled,
} from '../../../lib/api/settingsAuthentication'
import type { OidcAdminConfig, OidcConfigPayload } from '../../../lib/api/settingsAuthentication'
import { OidcConfigurationForm } from './authentication/OidcConfigurationForm'
import './authentication/authentication.css'

const QUERY_KEY = ['settings', 'authentication', 'oidc'] as const

function formFromConfig(config: OidcAdminConfig): OidcConfigPayload {
  return {
    issuer: config.issuer,
    client_id: config.client_id,
    client_secret: config.client_secret,
    redirect_uri: config.redirect_uri || `${window.location.origin}/auth/oidc/callback`,
    scopes: config.scopes,
    username_claim: config.username_claim,
    groups_claim: config.groups_claim,
    admin_groups: config.admin_groups,
    user_groups: config.user_groups,
    allow_all_users: config.allow_all_users,
    allow_private_network: config.allow_private_network,
    provider_name: config.provider_name,
    button_label: config.button_label,
    auto_redirect: config.auto_redirect,
  }
}

export function AuthenticationSection() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<OidcConfigPayload | null>(null)
  const [message, setMessage] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null)
  const [initialAccessToken, setInitialAccessToken] = useState('')

  const configQuery = useQuery({ queryKey: QUERY_KEY, queryFn: getOidcAdminConfig, staleTime: 10_000 })
  const config = configQuery.data

  useEffect(() => {
    if (config) setForm(formFromConfig(config))
  }, [config])

  useEffect(() => {
    const handleTestResult = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== 'nutify-oidc-test') return
      setMessage({ tone: event.data.success ? 'success' : 'danger', text: String(event.data.message || 'SSO test finished') })
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    }
    window.addEventListener('message', handleTestResult)
    return () => window.removeEventListener('message', handleTestResult)
  }, [queryClient])

  const mutation = useMutation({
    mutationFn: async (operation: () => Promise<OidcAdminConfig>) => operation(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    },
    onError: (error: unknown) => setMessage({ tone: 'danger', text: error instanceof Error ? error.message : 'Authentication update failed' }),
  })

  const run = (successMessage: string, operation: () => Promise<OidcAdminConfig>) => {
    setMessage(null)
    mutation.mutate(operation, { onSuccess: () => setMessage({ tone: 'success', text: successMessage }) })
  }

  const busy = configQuery.isLoading || mutation.isPending
  const statusLabel = useMemo(() => {
    if (!config) return 'Loading'
    if (config.source_error) return 'Configuration error'
    if (config.enabled) return 'SSO active'
    if (config.configured) return 'Draft saved'
    return 'Local login only'
  }, [config])

  if (configQuery.isError || !config || !form) {
    return <div className="combined_card"><div className="options_alert">{configQuery.isError ? 'Unable to load authentication settings.' : 'Loading authentication settings...'}</div></div>
  }

  return (
    <div className="authentication-shell">
      <header className="authentication-hero">
        <div>
          <span className="auth-kicker">Access control</span>
          <h2>Authentication</h2>
          <p>Keep Nutify accounts available, or add your organization&apos;s OpenID Connect sign-in.</p>
        </div>
        <div className={`auth-status-pill ${config.enabled ? 'active' : ''}`}><span />{statusLabel}</div>
      </header>

      {message ? <div className={`auth-message ${message.tone}`}>{message.text}</div> : null}
      {config.source_error ? <div className="auth-message danger">{config.source_error}</div> : null}

      <div className="auth-method-strip">
        <article className="auth-method-card active">
          <i className="fas fa-user-lock" />
          <div><h3>Nutify account</h3><p>Built-in username and password. Always available as the recovery path.</p></div>
          <span>Active</span>
        </article>
        <article className={`auth-method-card ${config.enabled ? 'active' : ''}`}>
          <i className="fas fa-fingerprint" />
          <div><h3>Single Sign-On</h3><p>{config.provider_name || 'OpenID Connect'} identity provider.</p></div>
          <span>{config.enabled ? 'Active' : 'Optional'}</span>
        </article>
      </div>

      {!config.editable ? (
        <section className="auth-config-panel auth-readonly-panel">
          <i className="fas fa-lock" />
          <div><h3>Managed by environment</h3><p>This deployment uses <code>OIDC_CONFIG_SOURCE=environment</code>. Change OIDC values in the container environment and restart Nutify.</p></div>
        </section>
      ) : (
        <OidcConfigurationForm
          config={config}
          form={form}
          busy={busy}
          initialAccessToken={initialAccessToken}
          onInitialAccessToken={setInitialAccessToken}
          onField={(key, value) => setForm((current) => current ? { ...current, [key]: value } : current)}
          onSave={() => run('Configuration saved. Continue with provider discovery.', () => saveOidcAdminConfig(form))}
          onDiscover={() => {
            setMessage(null)
            mutation.mutate(async () => (await discoverOidcProvider()).configuration, { onSuccess: () => setMessage({ tone: 'success', text: 'Provider discovery succeeded. Run the browser sign-in test.' }) })
          }}
          onRegister={() => run('Nutify client registered. The one-time token was not stored.', () => registerOidcClient({ ...form, initial_access_token: initialAccessToken }).finally(() => setInitialAccessToken('')))}
          onTest={() => {
            const popup = window.open('/auth/oidc/test/login', 'nutify-oidc-test', 'popup=yes,width=720,height=760')
            if (!popup) setMessage({ tone: 'danger', text: 'Allow pop-ups for Nutify to run the SSO browser test.' })
          }}
          onEnable={(enabled) => run(enabled ? 'Single Sign-On enabled.' : 'Single Sign-On disabled. Local login remains available.', () => setOidcEnabled(enabled))}
          onDelete={() => {
            if (window.confirm('Delete the saved Single Sign-On configuration? Local login will remain available.')) run('Single Sign-On configuration deleted.', deleteOidcAdminConfig)
          }}
        />
      )}
    </div>
  )
}
