/**
 * Adminsection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import {
  changeOwnPassword,
  changeOwnUsername,
  createAdminUser,
  deleteAdminUser,
  getUserOptionsTabs,
  getUserPermissions,
  listAdminUsers,
  updateUserOptionsTabs,
  updateUserPassword,
  updateUserPermissions,
  updateUserRole,
  type UserOptionsTabs,
  type UserPagePermissions,
} from '../../../lib/api/admin'
import { useAppStore } from '../../../store/appStore'
import {
  createDefaultOptionsTabs,
  createDefaultPagePermissions,
  formatDateTime,
  formatRole,
  roleBadgeClass,
  type MessageState,
} from './adminSectionShared'
import { AdminActionModal, type DynamicModalState } from './admin/AdminActionModal'
import { AdminPermissionModals } from './admin/AdminPermissionModals'

export function AdminSection() {
  const queryClient = useQueryClient()
  const bootstrap = useAppStore((state) => state.bootstrap)
  const currentUser = bootstrap?.auth.current_user
  const isAdmin = Boolean(bootstrap?.settings?.is_admin)

  const [message, setMessage] = useState<MessageState>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [dynamicModal, setDynamicModal] = useState<DynamicModalState>(null)
  const [permissionsModalUser, setPermissionsModalUser] = useState<(typeof users)[number] | null>(null)
  const [optionsTabsModalOpen, setOptionsTabsModalOpen] = useState(false)
  const [permissionsDraft, setPermissionsDraft] = useState<UserPagePermissions>(createDefaultPagePermissions())
  const [optionsTabsDraft, setOptionsTabsDraft] = useState<UserOptionsTabs>(createDefaultOptionsTabs())
  const [hasAnyOptionsTabEnabled, setHasAnyOptionsTabEnabled] = useState(false)

  const [addUserForm, setAddUserForm] = useState({
    username: '',
    password: '',
    role: 'user' as 'administrator' | 'user',
  })
  const [userPasswordDraft, setUserPasswordDraft] = useState('')
  const [userRoleDraft, setUserRoleDraft] = useState<'administrator' | 'user'>('user')
  const [personalPasswordForm, setPersonalPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  })
  const [personalUsernameForm, setPersonalUsernameForm] = useState({
    newUsername: '',
    password: '',
  })

  const usersQuery = useQuery({
    queryKey: ['settings', 'admin', 'users'],
    queryFn: listAdminUsers,
    enabled: isAdmin,
    refetchInterval: 30_000,
  })
  const users = useMemo(() => usersQuery.data ?? [], [usersQuery.data])

  const setError = (error: unknown, fallback: string) => {
    const text = error instanceof Error ? error.message : fallback
    setMessage({ tone: 'error', text })
  }

  const withBusy = async (key: string, task: () => Promise<void>) => {
    setBusyKey(key)
    try {
      await task()
    } finally {
      setBusyKey(null)
    }
  }

  const refreshUsers = async () => {
    await queryClient.invalidateQueries({ queryKey: ['settings', 'admin', 'users'] })
  }

  const openDynamicModal = (modal: DynamicModalState) => {
    setDynamicModal(modal)
    setMessage(null)
    if (modal?.type === 'add-user') setAddUserForm({ username: '', password: '', role: 'user' })
    if (modal?.type === 'change-user-password') setUserPasswordDraft('')
    if (modal?.type === 'change-user-role') setUserRoleDraft(modal.user.role === 'administrator' ? 'administrator' : 'user')
    if (modal?.type === 'change-personal-password') setPersonalPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' })
    if (modal?.type === 'change-personal-username') setPersonalUsernameForm({ newUsername: '', password: '' })
  }

  const closeAllModals = () => {
    setDynamicModal(null)
    setPermissionsModalUser(null)
    setOptionsTabsModalOpen(false)
  }

  const openPermissionsModal = async (user: (typeof users)[number]) => {
    if (!isAdmin) return
    await withBusy(`permissions:${user.id}`, async () => {
      try {
        const [permissions, tabs] = await Promise.all([getUserPermissions(user.id), getUserOptionsTabs(user.id)])
        const hasAnyTab = Object.values(tabs).some(Boolean)
        setHasAnyOptionsTabEnabled(hasAnyTab)
        setOptionsTabsDraft(tabs)
        setPermissionsDraft({
          ...permissions,
          options: user.role === 'administrator' ? true : hasAnyTab ? true : false,
        })
        setPermissionsModalUser(user)
      } catch (error) {
        setError(error, 'Failed to load user permissions')
      }
    })
  }

  const handleCreateUser = async () => {
    const username = addUserForm.username.trim()
    if (!username || !addUserForm.password) return setMessage({ tone: 'error', text: 'All fields are required' })
    if (username.length < 3) return setMessage({ tone: 'error', text: 'Username must be at least 3 characters long' })
    if (addUserForm.password.length < 6) return setMessage({ tone: 'error', text: 'Password must be at least 6 characters long' })
    await withBusy('create-user', async () => {
      try {
        await createAdminUser({ username, password: addUserForm.password, role: addUserForm.role })
        setMessage({ tone: 'success', text: 'User created successfully' })
        setDynamicModal(null)
        await refreshUsers()
      } catch (error) {
        setError(error, 'Failed to create user')
      }
    })
  }

  const handleUserPasswordChange = async () => {
    if (!dynamicModal || dynamicModal.type !== 'change-user-password') return
    if (userPasswordDraft.length < 6) return setMessage({ tone: 'error', text: 'Password must be at least 6 characters long' })
    await withBusy(`password:${dynamicModal.user.id}`, async () => {
      try {
        await updateUserPassword(dynamicModal.user.id, userPasswordDraft)
        setMessage({ tone: 'success', text: 'User password updated successfully' })
        setDynamicModal(null)
        await refreshUsers()
      } catch (error) {
        setError(error, 'Failed to update password')
      }
    })
  }

  const handleUserRoleChange = async () => {
    if (!dynamicModal || dynamicModal.type !== 'change-user-role') return
    await withBusy(`role:${dynamicModal.user.id}`, async () => {
      try {
        await updateUserRole(dynamicModal.user.id, userRoleDraft)
        setMessage({ tone: 'success', text: 'User role updated successfully' })
        setDynamicModal(null)
        await refreshUsers()
      } catch (error) {
        setError(error, 'Failed to update role')
      }
    })
  }

  const handleDeleteUser = async (user: (typeof users)[number]) => {
    if (user.id === 1 || user.id === Number(currentUser?.id)) return
    if (!window.confirm(`Are you sure you want to delete user "${user.username}"?`)) return
    await withBusy(`delete:${user.id}`, async () => {
      try {
        await deleteAdminUser(user.id)
        setMessage({ tone: 'success', text: 'User deleted successfully' })
        await refreshUsers()
      } catch (error) {
        setError(error, 'Failed to delete user')
      }
    })
  }

  const handleSavePermissions = async () => {
    if (!permissionsModalUser) return
    await withBusy(`save-permissions:${permissionsModalUser.id}`, async () => {
      try {
        await updateUserPermissions(permissionsModalUser.id, permissionsDraft)
        setMessage({ tone: 'success', text: 'User permissions updated successfully' })
        setPermissionsModalUser(null)
        await refreshUsers()
      } catch (error) {
        setError(error, 'Failed to update user permissions')
      }
    })
  }

  const handleSaveOptionsTabs = async () => {
    if (!permissionsModalUser) return
    await withBusy(`save-tabs:${permissionsModalUser.id}`, async () => {
      try {
        await updateUserOptionsTabs(permissionsModalUser.id, optionsTabsDraft)
        const hasAnyTab = Object.values(optionsTabsDraft).some(Boolean)
        setHasAnyOptionsTabEnabled(hasAnyTab)
        setPermissionsDraft((current) => ({ ...current, options: permissionsModalUser.role === 'administrator' ? true : hasAnyTab }))
        setMessage({ tone: 'success', text: 'Options tabs configuration saved successfully' })
        setOptionsTabsModalOpen(false)
      } catch (error) {
        setError(error, 'Failed to save options tabs configuration')
      }
    })
  }

  const handlePersonalPasswordChange = async () => {
    const { currentPassword, newPassword, confirmPassword } = personalPasswordForm
    if (!currentPassword || !newPassword || !confirmPassword) return setMessage({ tone: 'error', text: 'All fields are required' })
    if (newPassword.length < 6) return setMessage({ tone: 'error', text: 'New password must be at least 6 characters long' })
    if (newPassword !== confirmPassword) return setMessage({ tone: 'error', text: 'New passwords do not match' })
    await withBusy('change-personal-password', async () => {
      try {
        await changeOwnPassword(currentPassword, newPassword)
        setMessage({ tone: 'success', text: 'Password updated successfully' })
        setDynamicModal(null)
      } catch (error) {
        setError(error, 'Failed to update password')
      }
    })
  }

  const handlePersonalUsernameChange = async () => {
    const nextUsername = personalUsernameForm.newUsername.trim()
    if (!nextUsername || !personalUsernameForm.password) return setMessage({ tone: 'error', text: 'All fields are required' })
    if (nextUsername.length < 3) return setMessage({ tone: 'error', text: 'Username must be at least 3 characters long' })
    await withBusy('change-personal-username', async () => {
      try {
        await changeOwnUsername(nextUsername, personalUsernameForm.password)
        setMessage({ tone: 'success', text: 'Username updated successfully. Reloading session...' })
        setDynamicModal(null)
        window.setTimeout(() => window.location.reload(), 500)
      } catch (error) {
        setError(error, 'Failed to update username')
      }
    })
  }

  const optionsPermissionDisabled = permissionsModalUser?.role !== 'administrator' && !hasAnyOptionsTabEnabled
  const showConfigureOptionsButton = permissionsModalUser?.role !== 'administrator'

  return (
    <>
      <div id="adminUserManagement" className="options_card" style={{ display: isAdmin ? 'block' : 'none' }}>
        <div className="card_header"><div className="notification_header"><h2><i className="fas fa-users-cog" /> User Management</h2></div><p className="card_subtitle">Manage system users and their permissions</p></div>
        <div id="usersTableContainer"><div className="users-table-wrapper"><div className="users-table-header"><h3>System Users</h3><button type="button" id="addUserBtn" className="options_btn" onClick={() => openDynamicModal({ type: 'add-user' })}><i className="fas fa-plus" /> Add User</button></div><div className="users-table"><table><thead><tr><th>ID</th><th>Username</th><th>Role</th><th>Last Login</th><th>Created</th><th>Actions</th></tr></thead><tbody>{(usersQuery.isLoading ? [] : users).map((user) => (<tr key={user.id} data-user-id={user.id}><td>{user.id}</td><td>{user.id === 1 ? <span className="non-clickable-username">{user.username}</span> : <a href="#" className="clickable-username" onClick={(event) => { event.preventDefault(); void openPermissionsModal(user) }}>{user.username}</a>}</td><td><span className={`role-badge ${roleBadgeClass(user.role)}`}>{formatRole(user.role)}</span></td><td>{user.last_login ? formatDateTime(user.last_login) : 'Never'}</td><td>{user.created_at ? formatDateTime(user.created_at) : 'Unknown'}</td><td className="actions"><button type="button" className="options_btn options_btn_small" onClick={() => openDynamicModal({ type: 'change-user-password', user })}><i className="fas fa-key" /> Change Password</button>{user.id !== 1 ? <button type="button" className="options_btn options_btn_small" onClick={() => openDynamicModal({ type: 'change-user-role', user })}><i className="fas fa-user-tag" /> Change Role</button> : null}{user.id !== 1 && user.id !== Number(currentUser?.id) ? <button type="button" className="options_btn options_btn_small options_btn_danger" onClick={() => void handleDeleteUser(user)}><i className="fas fa-trash" /> Delete</button> : null}</td></tr>))}</tbody></table></div></div></div>
      </div>

      <div id="regularUserSection">
        <div className="options_card mt-4">
          <div className="card_header"><div className="notification_header"><h2><i className="fas fa-user-circle" /> Current User</h2></div><p className="card_subtitle">Your account information</p></div>
          <div id="options_admin_status" className={`options_alert ${message ? '' : 'hidden'} ${message?.tone === 'error' ? 'danger' : ''}`}>{message ? message.text : ''}</div>
          <div className="options_nutify_grid">
            <div className="options_notification_card"><div className="options_nutify_header"><div className="options_nutify_icon"><i className="fas fa-user" /></div><div className="options_nutify_title_container"><span className="options_nutify_title">Username</span><span className="options_nutify_description" id="currentUsername">{String(currentUser?.username || 'N/A')}</span></div></div></div>
            <div className="options_notification_card"><div className="options_nutify_header"><div className="options_nutify_icon"><i className="fas fa-id-card" /></div><div className="options_nutify_title_container"><span className="options_nutify_title">User ID</span><span className="options_nutify_description" id="currentUserId">{Number.isFinite(Number(currentUser?.id)) ? Number(currentUser?.id) : 'N/A'}</span></div></div></div>
            <div className="options_notification_card"><div className="options_nutify_header"><div className="options_nutify_icon"><i className="fas fa-user-tag" /></div><div className="options_nutify_title_container"><span className="options_nutify_title">User Role</span><span className="options_nutify_description" id="currentUserRole">{formatRole(String(currentUser?.role ?? 'user'))}</span></div></div></div>
            <div className="options_notification_card"><div className="options_nutify_header"><div className="options_nutify_icon"><i className="fas fa-clock" /></div><div className="options_nutify_title_container"><span className="options_nutify_title">Last Login</span><span className="options_nutify_description" id="currentUserLastLogin">{typeof currentUser?.last_login === 'string' && currentUser.last_login ? formatDateTime(currentUser.last_login) : 'Never'}</span></div></div></div>
          </div>
          <div id="currentUserInfo" className="options_nutify_body" />
        </div>

        <div className="options_card mt-4">
          <div className="card_header"><div className="notification_header"><h2><i className="fas fa-user-cog" /> Personal Account</h2></div><p className="card_subtitle">Manage your personal account settings</p></div>
          <div className="options_notification_card"><div className="options_nutify_header"><div className="options_nutify_icon"><i className="fas fa-key" /></div><div className="options_nutify_title_container"><span className="options_nutify_title">Change Password</span><span className="options_nutify_description">Update your account password</span></div><button type="button" className="options_btn" onClick={() => openDynamicModal({ type: 'change-personal-password' })}><i className="fas fa-key" /> Change Password</button></div></div>
          <div className="options_notification_card"><div className="options_nutify_header"><div className="options_nutify_icon"><i className="fas fa-user-edit" /></div><div className="options_nutify_title_container"><span className="options_nutify_title">Change Username</span><span className="options_nutify_description">Update your account username</span></div><button type="button" className="options_btn" onClick={() => openDynamicModal({ type: 'change-personal-username' })}><i className="fas fa-user-edit" /> Change Username</button></div></div>
        </div>
      </div>

      <AdminPermissionModals
        permissionsModalUser={permissionsModalUser}
        permissionsDraft={permissionsDraft}
        setPermissionsDraft={setPermissionsDraft}
        optionsTabsDraft={optionsTabsDraft}
        setOptionsTabsDraft={setOptionsTabsDraft}
        optionsTabsModalOpen={optionsTabsModalOpen}
        setOptionsTabsModalOpen={setOptionsTabsModalOpen}
        optionsPermissionDisabled={Boolean(optionsPermissionDisabled)}
        showConfigureOptionsButton={Boolean(showConfigureOptionsButton)}
        busyKey={busyKey}
        onClosePermissionsModal={() => setPermissionsModalUser(null)}
        onSavePermissions={handleSavePermissions}
        onSaveOptionsTabs={handleSaveOptionsTabs}
      />

      <AdminActionModal
        dynamicModal={dynamicModal}
        busyKey={busyKey}
        closeAllModals={closeAllModals}
        addUserForm={addUserForm}
        setAddUserForm={setAddUserForm}
        userPasswordDraft={userPasswordDraft}
        setUserPasswordDraft={setUserPasswordDraft}
        userRoleDraft={userRoleDraft}
        setUserRoleDraft={setUserRoleDraft}
        personalPasswordForm={personalPasswordForm}
        setPersonalPasswordForm={setPersonalPasswordForm}
        personalUsernameForm={personalUsernameForm}
        setPersonalUsernameForm={setPersonalUsernameForm}
        onCreateUser={handleCreateUser}
        onChangeUserPassword={handleUserPasswordChange}
        onChangeUserRole={handleUserRoleChange}
        onChangePersonalPassword={handlePersonalPasswordChange}
        onChangePersonalUsername={handlePersonalUsernameChange}
      />
    </>
  )
}
