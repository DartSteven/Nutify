/**
 * Adminpage.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { logout } from '../../lib/api/auth'
import { PageHeader } from '../../components/PageHeader'
import { useAppStore } from '../../store/appStore'
import {
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  updateUserPassword,
  updateUserRole,
} from '../../lib/api/admin'

export function AdminPage() {
  const navigate = useNavigate()
  const bootstrap = useAppStore((state) => state.bootstrap)
  const user = bootstrap?.auth.current_user
  const [message, setMessage] = useState<string | null>(null)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<'administrator' | 'user'>('user')
  const [passwordDraft, setPasswordDraft] = useState<Record<number, string>>({})

  const { data: users = [], refetch, isLoading } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: listAdminUsers,
    refetchInterval: 30_000,
  })

  const handleLogout = async () => {
    await logout()
    navigate('/auth/login', { replace: true })
    window.location.href = '/auth/login'
  }

  const handleCreate = async () => {
    setMessage(null)
    try {
      await createAdminUser({ username: newUsername, password: newPassword, role: newRole })
      setMessage('User created successfully.')
      setNewUsername('')
      setNewPassword('')
      setNewRole('user')
      await refetch()
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Failed to create user')
    }
  }

  const handleRoleUpdate = async (userId: number, role: 'administrator' | 'user') => {
    setMessage(null)
    try {
      await updateUserRole(userId, role)
      setMessage('Role updated successfully.')
      await refetch()
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Failed to update role')
    }
  }

  const handlePasswordUpdate = async (userId: number) => {
    const password = passwordDraft[userId]
    if (!password) {
      setMessage('Insert a password before saving.')
      return
    }
    setMessage(null)
    try {
      await updateUserPassword(userId, password)
      setPasswordDraft((current) => ({ ...current, [userId]: '' }))
      setMessage('Password updated successfully.')
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Failed to update password')
    }
  }

  const handleDelete = async (userId: number) => {
    setMessage(null)
    try {
      await deleteAdminUser(userId)
      setMessage('User deleted successfully.')
      await refetch()
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Failed to delete user')
    }
  }

  return (
    <section className="space-y-4">
      <PageHeader title="Administration" subtitle="Manage dashboard users and credentials." />

      <article className="card-base space-y-3">
        <div className="text-sm text-slate-300">Signed in as: {user?.username ?? 'Unknown user'}</div>
        <div className="text-sm text-slate-500">Role: {user?.role ?? 'Unknown'}</div>
        {message ? <p className="text-sm text-cyan-200">{message}</p> : null}
        <button className="btn-danger" type="button" onClick={() => void handleLogout()}>
          Sign out
        </button>
      </article>

      <article className="card-base space-y-4">
        <h2 className="text-xl font-semibold text-slate-100">Create User</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="field-group">
            <span className="field-label">Username</span>
            <input className="input-base" value={newUsername} onChange={(event) => setNewUsername(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Password</span>
            <input
              className="input-base"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          <label className="field-group">
            <span className="field-label">Role</span>
            <select
              className="input-base"
              value={newRole}
              onChange={(event) => setNewRole(event.target.value === 'administrator' ? 'administrator' : 'user')}
            >
              <option value="user">User</option>
              <option value="administrator">Administrator</option>
            </select>
          </label>
        </div>
        <button className="btn-primary" type="button" onClick={() => void handleCreate()}>
          Create user
        </button>
      </article>

      <article className="card-base space-y-4">
        <h2 className="text-xl font-semibold text-slate-100">Users</h2>
        {isLoading ? <p className="text-sm text-slate-400">Loading users...</p> : null}
        <div className="space-y-3">
          {users.map((row) => (
            <div key={row.id} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-slate-100">
                    {row.username} <span className="text-xs text-slate-500">(ID {row.id})</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    Created: {row.created_at ?? '-'} | Last login: {row.last_login ?? '-'}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    className="input-base w-auto"
                    value={row.role === 'administrator' ? 'administrator' : 'user'}
                    onChange={(event) =>
                      void handleRoleUpdate(
                        row.id,
                        event.target.value === 'administrator' ? 'administrator' : 'user',
                      )
                    }
                  >
                    <option value="user">User</option>
                    <option value="administrator">Administrator</option>
                  </select>
                  <button
                    className="rounded-lg border border-rose-500/40 px-3 py-2 text-sm text-rose-200 hover:border-rose-400"
                    type="button"
                    onClick={() => void handleDelete(row.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  className="input-base max-w-xs"
                  type="password"
                  placeholder="New password"
                  value={passwordDraft[row.id] ?? ''}
                  onChange={(event) =>
                    setPasswordDraft((current) => ({
                      ...current,
                      [row.id]: event.target.value,
                    }))
                  }
                />
                <button className="btn-primary" type="button" onClick={() => void handlePasswordUpdate(row.id)}>
                  Update password
                </button>
              </div>
            </div>
          ))}
          {!isLoading && users.length === 0 ? <p className="text-sm text-slate-400">No active users found.</p> : null}
        </div>
      </article>
    </section>
  )
}
