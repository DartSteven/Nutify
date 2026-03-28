/**
 * Adminpermissionmodals.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { Dispatch, SetStateAction } from 'react'

import type { AdminUser, UserOptionsTabs, UserPagePermissions } from '../../../../lib/api/admin'
import { OPTIONS_TAB_LABELS, PAGE_PERMISSION_LABELS } from '../adminSectionShared'

type Props = {
  permissionsModalUser: AdminUser | null
  permissionsDraft: UserPagePermissions
  setPermissionsDraft: Dispatch<SetStateAction<UserPagePermissions>>
  optionsTabsDraft: UserOptionsTabs
  setOptionsTabsDraft: Dispatch<SetStateAction<UserOptionsTabs>>
  optionsTabsModalOpen: boolean
  setOptionsTabsModalOpen: (value: boolean) => void
  optionsPermissionDisabled: boolean
  showConfigureOptionsButton: boolean
  busyKey: string | null
  onClosePermissionsModal: () => void
  onSavePermissions: () => Promise<void>
  onSaveOptionsTabs: () => Promise<void>
}

export function AdminPermissionModals({
  permissionsModalUser,
  permissionsDraft,
  setPermissionsDraft,
  optionsTabsDraft,
  setOptionsTabsDraft,
  optionsTabsModalOpen,
  setOptionsTabsModalOpen,
  optionsPermissionDisabled,
  showConfigureOptionsButton,
  busyKey,
  onClosePermissionsModal,
  onSavePermissions,
  onSaveOptionsTabs,
}: Props) {
  return (
    <>
      <div id="userPermissionsModal" className="modal" style={{ display: permissionsModalUser ? 'block' : 'none' }}>
        <div className="modal-content">
          <div className="modal-header">
            <h3><i className="fas fa-lock" /> User Page Permissions</h3>
          </div>
          <div className="modal-body">
            <div style={{ marginBottom: '1rem' }}>
              <strong>User: <span id="permissionUserName">{permissionsModalUser?.username ?? ''}</span></strong>
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <p className="card_subtitle">Select which pages this user can access:</p>
            </div>
            <div className="permissions-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem' }}>
              {PAGE_PERMISSION_LABELS.map((entry) => (
                <div className="permission-item" key={entry.key}>
                  <label className="permission-label">
                    <input
                      type="checkbox"
                      id={`perm_${entry.key}`}
                      data-page={entry.key}
                      className="permission-checkbox"
                      checked={Boolean(permissionsDraft[entry.key])}
                      disabled={entry.key === 'options' ? optionsPermissionDisabled : false}
                      onChange={(event) => setPermissionsDraft((current) => ({ ...current, [entry.key]: event.target.checked }))}
                    />
                    <i className={`fas ${entry.icon}`} />
                    <span>{entry.label}</span>
                    {entry.key === 'options' && showConfigureOptionsButton ? (
                      <button type="button" className="configure-settings-btn" onClick={() => setOptionsTabsModalOpen(true)} title="Configure Options Tabs Access">
                        <i className="fas fa-cogs" />
                      </button>
                    ) : null}
                  </label>
                </div>
              ))}
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="options_btn_secondary" onClick={onClosePermissionsModal}>
              Cancel
            </button>
            <button type="button" className="options_btn" onClick={() => void onSavePermissions()} disabled={busyKey === `save-permissions:${permissionsModalUser?.id ?? -1}`}>
              <i className="fas fa-save" /> Save Permissions
            </button>
          </div>
        </div>
      </div>

      <div id="optionsTabsModal" className="modal" style={{ display: optionsTabsModalOpen ? 'block' : 'none' }}>
        <div className="modal-content">
          <div className="modal-header">
            <h3><i className="fas fa-cogs" /> Configure Options Tabs Access</h3>
          </div>
          <div className="modal-body">
            <div style={{ marginBottom: '1rem' }}>
              <strong>User: <span id="optionsTabsUserName">{permissionsModalUser?.username ?? ''}</span></strong>
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <p className="card_subtitle">Select which Options tabs this user can access:</p>
            </div>
            <div className="options-tabs-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
              {OPTIONS_TAB_LABELS.map((tab) => (
                <div className="options-tab-item" key={tab.key}>
                  <label className="options-tab-label">
                    <input
                      type="checkbox"
                      id={`tab_${tab.key}`}
                      data-tab={tab.key}
                      className="options-tab-checkbox"
                      checked={Boolean(optionsTabsDraft[tab.key])}
                      onChange={(event) => setOptionsTabsDraft((current) => ({ ...current, [tab.key]: event.target.checked }))}
                    />
                    <i className={`fas ${tab.icon}`} />
                    <span>{tab.label}</span>
                  </label>
                </div>
              ))}
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="options_btn_secondary" onClick={() => setOptionsTabsModalOpen(false)}>
              Cancel
            </button>
            <button type="button" className="options_btn" onClick={() => void onSaveOptionsTabs()} disabled={busyKey === `save-tabs:${permissionsModalUser?.id ?? -1}`}>
              <i className="fas fa-save" /> Save Configuration
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
