/**
 * Adminactionmodal.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { Dispatch, SetStateAction } from 'react'

import type { AdminUser } from '../../../../lib/api/admin'

export type DynamicModalState =
  | { type: 'add-user' }
  | { type: 'change-user-password'; user: AdminUser }
  | { type: 'change-user-role'; user: AdminUser }
  | { type: 'change-personal-password' }
  | { type: 'change-personal-username' }
  | null

type AddUserForm = {
  username: string
  password: string
  role: 'administrator' | 'user'
}

type PersonalPasswordForm = {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

type PersonalUsernameForm = {
  newUsername: string
  password: string
}

type Props = {
  dynamicModal: DynamicModalState
  busyKey: string | null
  closeAllModals: () => void
  addUserForm: AddUserForm
  setAddUserForm: Dispatch<SetStateAction<AddUserForm>>
  userPasswordDraft: string
  setUserPasswordDraft: Dispatch<SetStateAction<string>>
  userRoleDraft: 'administrator' | 'user'
  setUserRoleDraft: Dispatch<SetStateAction<'administrator' | 'user'>>
  personalPasswordForm: PersonalPasswordForm
  setPersonalPasswordForm: Dispatch<SetStateAction<PersonalPasswordForm>>
  personalUsernameForm: PersonalUsernameForm
  setPersonalUsernameForm: Dispatch<SetStateAction<PersonalUsernameForm>>
  onCreateUser: () => Promise<void>
  onChangeUserPassword: () => Promise<void>
  onChangeUserRole: () => Promise<void>
  onChangePersonalPassword: () => Promise<void>
  onChangePersonalUsername: () => Promise<void>
}

export function AdminActionModal({
  dynamicModal,
  busyKey,
  closeAllModals,
  addUserForm,
  setAddUserForm,
  userPasswordDraft,
  setUserPasswordDraft,
  userRoleDraft,
  setUserRoleDraft,
  personalPasswordForm,
  setPersonalPasswordForm,
  personalUsernameForm,
  setPersonalUsernameForm,
  onCreateUser,
  onChangeUserPassword,
  onChangeUserRole,
  onChangePersonalPassword,
  onChangePersonalUsername,
}: Props) {
  if (!dynamicModal) return null

  return (
    <div className="modal admin-modal" style={{ display: 'block' }}>
      <div className="modal-content">
        <div className="modal-header">
          <h5 className="modal-title">
            {dynamicModal.type === 'add-user' ? 'Add New User' : null}
            {dynamicModal.type === 'change-user-password'
              ? `Change Password for ${dynamicModal.user.username}`
              : null}
            {dynamicModal.type === 'change-user-role'
              ? `Change Role for ${dynamicModal.user.username}`
              : null}
            {dynamicModal.type === 'change-personal-password'
              ? 'Change Your Password'
              : null}
            {dynamicModal.type === 'change-personal-username'
              ? 'Change Your Username'
              : null}
          </h5>
          <button type="button" className="modal-close" onClick={closeAllModals}>
            <i className="fas fa-times" />
          </button>
        </div>
        <div className="modal-body">
          {dynamicModal.type === 'add-user' ? (
            <form id="addUserForm" onSubmit={(event) => { event.preventDefault(); void onCreateUser() }}>
              <div className="modal-form-group"><label htmlFor="newUserUsername">Username</label><input id="newUserUsername" value={addUserForm.username} onChange={(event) => setAddUserForm((current) => ({ ...current, username: event.target.value }))} placeholder="Enter username (min 3 characters)" /></div>
              <div className="modal-form-group"><label htmlFor="newUserPassword">Password</label><input id="newUserPassword" type="password" value={addUserForm.password} onChange={(event) => setAddUserForm((current) => ({ ...current, password: event.target.value }))} placeholder="Enter password (min 6 characters)" /></div>
              <div className="modal-form-group"><label htmlFor="newUserRole">User Role</label><select id="newUserRole" value={addUserForm.role} onChange={(event) => setAddUserForm((current) => ({ ...current, role: event.target.value === 'administrator' ? 'administrator' : 'user' }))}><option value="user">User</option><option value="administrator">Administrator</option></select></div>
              <div className="modal-actions"><button type="button" className="options_btn options_btn_secondary" onClick={closeAllModals}>Cancel</button><button type="submit" className="options_btn" disabled={busyKey === 'create-user'}><i className="fas fa-plus" /> Create User</button></div>
            </form>
          ) : null}
          {dynamicModal.type === 'change-user-password' ? (
            <form id="changeUserPasswordForm" onSubmit={(event) => { event.preventDefault(); void onChangeUserPassword() }}>
              <div className="modal-form-group"><label htmlFor="userNewPassword">New Password</label><input id="userNewPassword" type="password" value={userPasswordDraft} onChange={(event) => setUserPasswordDraft(event.target.value)} placeholder="Enter new password (min 6 characters)" /></div>
              <div className="modal-actions"><button type="button" className="options_btn options_btn_secondary" onClick={closeAllModals}>Cancel</button><button type="submit" className="options_btn" disabled={busyKey === `password:${dynamicModal.user.id}`}><i className="fas fa-key" /> Update Password</button></div>
            </form>
          ) : null}
          {dynamicModal.type === 'change-user-role' ? (
            <form id="changeUserRoleForm" onSubmit={(event) => { event.preventDefault(); void onChangeUserRole() }}>
              <div className="modal-form-group"><label htmlFor="userNewRole">User Role</label><select id="userNewRole" value={userRoleDraft} onChange={(event) => setUserRoleDraft(event.target.value === 'administrator' ? 'administrator' : 'user')}><option value="user">User</option><option value="administrator">Administrator</option></select></div>
              <div className="modal-actions"><button type="button" className="options_btn options_btn_secondary" onClick={closeAllModals}>Cancel</button><button type="submit" className="options_btn" disabled={busyKey === `role:${dynamicModal.user.id}`}><i className="fas fa-user-tag" /> Update Role</button></div>
            </form>
          ) : null}
          {dynamicModal.type === 'change-personal-password' ? (
            <form id="changePersonalPasswordForm" onSubmit={(event) => { event.preventDefault(); void onChangePersonalPassword() }}>
              <div className="modal-form-group"><label htmlFor="currentPersonalPassword">Current Password</label><input id="currentPersonalPassword" type="password" value={personalPasswordForm.currentPassword} onChange={(event) => setPersonalPasswordForm((current) => ({ ...current, currentPassword: event.target.value }))} placeholder="Enter your current password" /></div>
              <div className="modal-form-group"><label htmlFor="newPersonalPassword">New Password</label><input id="newPersonalPassword" type="password" value={personalPasswordForm.newPassword} onChange={(event) => setPersonalPasswordForm((current) => ({ ...current, newPassword: event.target.value }))} placeholder="Enter new password (min 6 characters)" /></div>
              <div className="modal-form-group"><label htmlFor="confirmPersonalPassword">Confirm New Password</label><input id="confirmPersonalPassword" type="password" value={personalPasswordForm.confirmPassword} onChange={(event) => setPersonalPasswordForm((current) => ({ ...current, confirmPassword: event.target.value }))} placeholder="Confirm new password" /></div>
              <div className="modal-actions"><button type="button" className="options_btn options_btn_secondary" onClick={closeAllModals}>Cancel</button><button type="submit" className="options_btn" disabled={busyKey === 'change-personal-password'}><i className="fas fa-save" /> Update Password</button></div>
            </form>
          ) : null}
          {dynamicModal.type === 'change-personal-username' ? (
            <form id="changePersonalUsernameForm" onSubmit={(event) => { event.preventDefault(); void onChangePersonalUsername() }}>
              <div className="modal-form-group"><label htmlFor="newPersonalUsername">New Username</label><input id="newPersonalUsername" value={personalUsernameForm.newUsername} onChange={(event) => setPersonalUsernameForm((current) => ({ ...current, newUsername: event.target.value }))} placeholder="Enter new username (min 3 characters)" /></div>
              <div className="modal-form-group"><label htmlFor="personalUsernamePassword">Current Password</label><input id="personalUsernamePassword" type="password" value={personalUsernameForm.password} onChange={(event) => setPersonalUsernameForm((current) => ({ ...current, password: event.target.value }))} placeholder="Enter your current password" /></div>
              <div className="modal-actions"><button type="button" className="options_btn options_btn_secondary" onClick={closeAllModals}>Cancel</button><button type="submit" className="options_btn" disabled={busyKey === 'change-personal-username'}><i className="fas fa-save" /> Update Username</button></div>
            </form>
          ) : null}
        </div>
      </div>
    </div>
  )
}
