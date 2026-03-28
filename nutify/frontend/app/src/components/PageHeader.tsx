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
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="page_header">
      <div className="page_title">
        <h1>{title}</h1>
        {subtitle ? <p className="page_subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page_actions">{actions}</div> : null}
    </div>
  )
}
