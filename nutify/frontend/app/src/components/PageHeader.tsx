/**
 * Pageheader.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  subtitle?: string
  actions?: ReactNode
  kicker?: string
  nextOnly?: boolean
}

export function PageHeader({ title, subtitle, actions, kicker = 'Nutify control', nextOnly = false }: PageHeaderProps) {
  return (
    <div className={['page_header', nextOnly ? 'page_header--next-only' : ''].join(' ').trim()}>
      <div className="page_title">
        <span className="page-kicker">{kicker}</span>
        <h1>{title}</h1>
        {subtitle ? <p className="page_subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page_actions">{actions}</div> : null}
      <span className="page-header-orbit" aria-hidden="true" />
    </div>
  )
}
