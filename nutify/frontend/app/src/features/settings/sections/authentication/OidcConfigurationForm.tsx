import type { OidcAdminConfig, OidcConfigPayload } from '../../../../lib/api/settingsAuthentication'

type Props = {
  config: OidcAdminConfig
  form: OidcConfigPayload
  busy: boolean
  initialAccessToken: string
  onField: <K extends keyof OidcConfigPayload>(key: K, value: OidcConfigPayload[K]) => void
  onInitialAccessToken: (value: string) => void
  onSave: () => void
  onDiscover: () => void
  onRegister: () => void
  onTest: () => void
  onEnable: (enabled: boolean) => void
  onDelete: () => void
}

function Field(props: {
  label: string
  value: string
  type?: string
  placeholder?: string
  hint?: string
  onChange: (value: string) => void
}) {
  return (
    <label className="auth-config-field">
      <span>{props.label}</span>
      <input
        type={props.type ?? 'text'}
        value={props.value}
        placeholder={props.placeholder}
        autoComplete="off"
        onChange={(event) => props.onChange(event.target.value)}
      />
      {props.hint ? <small>{props.hint}</small> : null}
    </label>
  )
}

export function OidcConfigurationForm(props: Props) {
  const { config, form, busy, onField } = props
  const canDiscover = Boolean(config.issuer && config.redirect_uri)
  const canTest = config.discovery_status === 'valid'
  const canEnable = canTest && config.verified

  return (
    <div className="auth-config-layout">
      <section className="auth-config-panel auth-config-primary">
        <div className="auth-config-heading">
          <span className="auth-step">01</span>
          <div>
            <h3>Connect your identity provider</h3>
            <p>Use any OpenID Connect provider that supports Authorization Code flow.</p>
          </div>
        </div>

        <div className="auth-config-grid">
          <Field
            label="Issuer URL"
            value={form.issuer}
            placeholder="https://sso.example.com/application/o/nutify/"
            hint="Nutify reads the provider discovery document automatically."
            onChange={(value) => onField('issuer', value)}
          />
          <Field
            label="Client ID"
            value={form.client_id}
            placeholder="nutify"
            onChange={(value) => onField('client_id', value)}
          />
          <Field
            label="Client Secret"
            value={form.client_secret}
            type="password"
            placeholder={config.has_client_secret ? 'Secret saved - leave unchanged' : 'Required confidential client secret'}
            hint="Stored encrypted. A blank value preserves an existing secret."
            onChange={(value) => onField('client_secret', value)}
          />
          <Field
            label="Callback URL"
            value={form.redirect_uri}
            hint="Add this exact URL to the provider's allowed redirect URIs."
            onChange={(value) => onField('redirect_uri', value)}
          />
          <Field label="Provider name" value={form.provider_name} onChange={(value) => onField('provider_name', value)} />
          <Field label="Login button label" value={form.button_label} onChange={(value) => onField('button_label', value)} />
        </div>
        <button
          type="button"
          className="auth-copy-link"
          onClick={() => void navigator.clipboard.writeText(form.redirect_uri)}
        >
          <i className="fas fa-copy" /> Copy callback URL
        </button>

        <details className="auth-advanced">
          <summary>Claims and access policy</summary>
          <div className="auth-config-grid">
            <Field label="Scopes" value={form.scopes} onChange={(value) => onField('scopes', value)} />
            <Field label="Username claim" value={form.username_claim} onChange={(value) => onField('username_claim', value)} />
            <Field label="Groups claim" value={form.groups_claim} onChange={(value) => onField('groups_claim', value)} />
            <Field label="Administrator groups" value={form.admin_groups} placeholder="nutify-admins" onChange={(value) => onField('admin_groups', value)} />
            <Field label="User groups" value={form.user_groups} placeholder="nutify-users" onChange={(value) => onField('user_groups', value)} />
          </div>
          <label className="auth-check-row">
            <input type="checkbox" checked={form.allow_all_users} onChange={(event) => onField('allow_all_users', event.target.checked)} />
            <span><strong>Allow all authenticated users</strong><small>Otherwise at least one configured group must match.</small></span>
          </label>
          <label className="auth-check-row auth-check-warning">
            <input type="checkbox" checked={form.allow_private_network} onChange={(event) => onField('allow_private_network', event.target.checked)} />
            <span><strong>Allow a private-network issuer</strong><small>Enable only for a trusted IdP on your LAN. Link-local metadata addresses remain blocked.</small></span>
          </label>
          <label className="auth-check-row">
            <input type="checkbox" checked={form.auto_redirect} onChange={(event) => onField('auto_redirect', event.target.checked)} />
            <span><strong>Redirect directly to SSO</strong><small>Emergency local login remains available at /auth/login?local=1.</small></span>
          </label>
        </details>

        <button className="auth-action auth-action-primary" type="button" disabled={busy} onClick={props.onSave}>
          <i className="fas fa-floppy-disk" /> Save configuration
        </button>
      </section>

      <aside className="auth-config-panel auth-validation-rail">
        <div className="auth-config-heading">
          <span className="auth-step">02</span>
          <div><h3>Validate before launch</h3><p>SSO cannot be enabled until every safety check passes.</p></div>
        </div>

        <ol className="auth-validation-list">
          <li className={config.configured ? 'complete' : ''}><i className="fas fa-key" /><span><strong>Credentials saved</strong><small>Encrypted at rest</small></span></li>
          <li className={config.discovery_status === 'valid' ? 'complete' : config.discovery_status === 'failed' ? 'failed' : ''}><i className="fas fa-satellite-dish" /><span><strong>Provider discovery</strong><small>{config.discovery_status === 'failed' ? config.discovery_error : config.discovery_status}</small></span></li>
          <li className={config.verified ? 'complete' : ''}><i className="fas fa-user-check" /><span><strong>Browser sign-in test</strong><small>{config.verified_at ? 'Identity and claims verified' : 'Not verified'}</small></span></li>
        </ol>

        <div className="auth-validation-actions">
          <button type="button" className="auth-action" disabled={busy || !canDiscover} onClick={props.onDiscover}><i className="fas fa-compass" /> Discover provider</button>
          <button type="button" className="auth-action" disabled={busy || !canTest} onClick={props.onTest}><i className="fas fa-arrow-up-right-from-square" /> Test SSO in browser</button>
          <button type="button" className={`auth-action ${config.enabled ? 'auth-action-danger' : 'auth-action-success'}`} disabled={busy || (!config.enabled && !canEnable)} onClick={() => props.onEnable(!config.enabled)}>
            <i className={`fas ${config.enabled ? 'fa-power-off' : 'fa-shield-halved'}`} /> {config.enabled ? 'Disable SSO' : 'Enable SSO'}
          </button>
        </div>

        {config.registration_supported ? (
          <div className="auth-registration-box">
            <span className="auth-kicker">Optional automation</span>
            <h4>Dynamic client registration</h4>
            <p>Your provider advertises registration support. It may require a one-time initial access token.</p>
            <input type="password" value={props.initialAccessToken} placeholder="Initial access token (optional)" onChange={(event) => props.onInitialAccessToken(event.target.value)} />
            <button type="button" className="auth-action" disabled={busy} onClick={props.onRegister}><i className="fas fa-wand-magic-sparkles" /> Register Nutify client</button>
          </div>
        ) : null}

        {config.configured ? <button type="button" className="auth-delete-link" disabled={busy} onClick={props.onDelete}>Delete SSO configuration</button> : null}
      </aside>
    </div>
  )
}
