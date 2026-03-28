/**
 * Apidocspage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../../components/PageHeader'
import { getApiCatalog, type ApiCatalog, type ApiCatalogRoute } from '../../lib/api/apiCatalog'
import { withTarget } from '../../lib/api/client'
import { useAppStore } from '../../store/appStore'

type MethodFilter = 'ALL' | 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

const METHOD_FILTERS: MethodFilter[] = ['ALL', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE']

function formatGeneratedAt(value: string | null): string {
  if (!value) {
    return 'Unavailable'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

function formatResponsePayload(payload: unknown): string {
  return JSON.stringify(payload ?? { message: 'Run a GET request to inspect payload.' }, null, 2)
}

export function ApiDocsPage() {
  const activeTargetId = useAppStore((state) => state.activeTargetId)

  const [catalog, setCatalog] = useState<ApiCatalog | null>(null)
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError, setCatalogError] = useState<string | null>(null)

  const [groupFilter, setGroupFilter] = useState('all')
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('ALL')
  const [searchTerm, setSearchTerm] = useState('')

  const [manualPath, setManualPath] = useState('')
  const [requestLoading, setRequestLoading] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [responsePayload, setResponsePayload] = useState<unknown>(null)

  const loadCatalog = async () => {
    setCatalogLoading(true)
    setCatalogError(null)
    try {
      const payload = await getApiCatalog()
      setCatalog(payload)
    } catch (error: unknown) {
      setCatalogError(error instanceof Error ? error.message : 'Failed to load API catalog')
    } finally {
      setCatalogLoading(false)
    }
  }

  useEffect(() => {
    void loadCatalog()
  }, [])

  useEffect(() => {
    if (manualPath.trim() || !catalog) {
      return
    }

    const firstGetRoute = catalog.groups.flatMap((group) => group.routes).find((route) => route.supports_get)
    if (firstGetRoute) {
      setManualPath(firstGetRoute.path)
    }
  }, [catalog, manualPath])

  const allRoutes = useMemo(() => catalog?.groups.flatMap((group) => group.routes) ?? [], [catalog])

  const groupOptions = useMemo(
    () =>
      catalog?.groups.map((group) => ({
        key: group.key,
        label: group.label,
      })) ?? [],
    [catalog],
  )

  const filteredGroups = useMemo(() => {
    if (!catalog) {
      return []
    }

    const normalizedSearch = searchTerm.trim().toLowerCase()

    return catalog.groups
      .filter((group) => groupFilter === 'all' || group.key === groupFilter)
      .map((group) => {
        const routes = group.routes.filter((route) => {
          const matchesMethod = methodFilter === 'ALL' || route.methods.includes(methodFilter)
          if (!matchesMethod) {
            return false
          }

          if (!normalizedSearch) {
            return true
          }

          const haystack = [route.path, route.summary, route.endpoint, route.module, route.function_name]
            .concat([route.access_label, route.access_detail, route.access_kind])
            .join(' ')
            .toLowerCase()
          return haystack.includes(normalizedSearch)
        })

        return {
          ...group,
          routes,
          route_count: routes.length,
        }
      })
      .filter((group) => group.routes.length > 0)
  }, [catalog, groupFilter, methodFilter, searchTerm])

  const filteredRouteCount = useMemo(
    () => filteredGroups.reduce((count, group) => count + group.routes.length, 0),
    [filteredGroups],
  )

  const selectedRoute = useMemo<ApiCatalogRoute | null>(
    () => allRoutes.find((route) => route.path === manualPath) ?? null,
    [allRoutes, manualPath],
  )

  const runnerDisabled = requestLoading || !manualPath.trim() || (selectedRoute?.path === manualPath && !selectedRoute.supports_get)

  const runGet = async (path: string) => {
    const trimmedPath = path.trim()
    if (!trimmedPath) {
      setRequestError('Enter a GET path to inspect.')
      setResponsePayload(null)
      return
    }

    setRequestLoading(true)
    setRequestError(null)

    try {
      const response = await fetch(withTarget(trimmedPath, activeTargetId), {
        credentials: 'same-origin',
      })
      const responseText = await response.text()
      let payload: unknown

      try {
        payload = responseText ? JSON.parse(responseText) : {}
      } catch {
        payload = { raw: responseText || '(empty response)' }
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setResponsePayload(payload)
    } catch (error: unknown) {
      setRequestError(error instanceof Error ? error.message : 'Request failed')
      setResponsePayload(null)
    } finally {
      setRequestLoading(false)
    }
  }

  return (
    <section className="space-y-4">
      <PageHeader
        title="API Explorer"
        subtitle={
          catalog
            ? `Dynamic catalog of ${catalog.total_routes} registered API routes.`
            : 'Dynamic catalog of the registered Nutify API routes.'
        }
        actions={
          <button className="btn-primary" type="button" onClick={() => void loadCatalog()} disabled={catalogLoading}>
            {catalogLoading ? 'Refreshing...' : 'Refresh Catalog'}
          </button>
        }
      />

      <article className="card-base space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="table_info_card">
            <div className="card_subtitle">Visible routes</div>
            <strong>{filteredRouteCount}</strong>
          </div>
          <div className="table_info_card">
            <div className="card_subtitle">Groups</div>
            <strong>{catalog?.total_groups ?? 0}</strong>
          </div>
          <div className="table_info_card">
            <div className="card_subtitle">Protected routes</div>
            <strong>{allRoutes.filter((route) => route.access_kind !== 'public').length}</strong>
          </div>
          <div className="table_info_card">
            <div className="card_subtitle">Generated</div>
            <strong>{formatGeneratedAt(catalog?.generated_at ?? null)}</strong>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <label className="field-group">
            <span className="field-label">Search routes</span>
            <input
              className="input-base"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Path, summary, endpoint, module"
            />
          </label>

          <label className="field-group">
            <span className="field-label">Group</span>
            <select className="input-base" value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
              <option value="all">All groups</option>
              {groupOptions.map((group) => (
                <option key={group.key} value={group.key}>
                  {group.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field-group">
            <span className="field-label">Method</span>
            <select className="input-base" value={methodFilter} onChange={(event) => setMethodFilter(event.target.value as MethodFilter)}>
              {METHOD_FILTERS.map((method) => (
                <option key={method} value={method}>
                  {method === 'ALL' ? 'All methods' : method}
                </option>
              ))}
            </select>
          </label>
        </div>
      </article>

      <article className="card-base space-y-4">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <label className="field-group">
            <span className="field-label">GET inspector</span>
            <input
              className="input-base"
              value={manualPath}
              onChange={(event) => setManualPath(event.target.value)}
              placeholder="/api/data/all"
            />
          </label>
          <button className="btn-primary" type="button" disabled={runnerDisabled} onClick={() => void runGet(manualPath)}>
            {requestLoading ? 'Running...' : 'Run GET'}
          </button>
        </div>

        <div className="space-y-1">
          <p className="card_subtitle">Select a route below to load it into the inspector. The runner is limited to GET endpoints.</p>
          {selectedRoute ? (
            <p className="card_subtitle">
              Selected: <strong>{selectedRoute.path}</strong> | Methods: {selectedRoute.methods.join(', ')}
            </p>
          ) : null}
          {selectedRoute && !selectedRoute.supports_get ? (
            <p className="card_subtitle">This route does not expose GET. Use the catalog for reference only.</p>
          ) : null}
          {requestError ? <p className="card_subtitle">{requestError}</p> : null}
        </div>

        <div className="events_table_container">
          <pre className="max-h-[340px] overflow-auto p-4 text-xs">{formatResponsePayload(responsePayload)}</pre>
        </div>
      </article>

      {catalogLoading ? <div className="empty-state">Loading registered API routes...</div> : null}
      {!catalogLoading && catalogError ? <div className="empty-state">{catalogError}</div> : null}
      {!catalogLoading && !catalogError && filteredGroups.length === 0 ? <div className="empty-state">No routes matched the current filters.</div> : null}

      {!catalogLoading && !catalogError
        ? filteredGroups.map((group) => (
            <article key={group.key} className="card-base space-y-3">
              <div>
                <h2>{group.label}</h2>
                <p className="card_subtitle">{group.route_count} routes in this group.</p>
              </div>

              <div className="events_table_container">
                <table className="events_table">
                  <thead>
                    <tr>
                      <th>Path</th>
                      <th>Methods</th>
                      <th>Summary</th>
                      <th>Access</th>
                      <th>Path Params</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.routes.map((route) => (
                      <tr
                        key={`${route.endpoint}:${route.path}`}
                        onClick={() => setManualPath(route.path)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            setManualPath(route.path)
                          }
                        }}
                        tabIndex={0}
                      >
                        <td>
                          <code>{route.path}</code>
                          {manualPath === route.path ? <div className="card_subtitle">Loaded in GET inspector</div> : null}
                        </td>
                        <td>{route.methods.join(', ')}</td>
                        <td>{route.summary}</td>
                        <td>
                          <div>{route.access_label}</div>
                          <div className="card_subtitle">{route.access_detail}</div>
                        </td>
                        <td>{route.path_params.length > 0 ? route.path_params.join(', ') : 'None'}</td>
                        <td>
                          <div>{route.endpoint}</div>
                          <div className="card_subtitle">
                            {route.function_name ? `${route.module}.${route.function_name}` : route.module}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          ))
        : null}
    </section>
  )
}
