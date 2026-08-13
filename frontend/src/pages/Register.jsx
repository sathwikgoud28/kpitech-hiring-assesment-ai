import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth'
import { Alert } from '../components/ui'

export default function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'candidate',
    company_name: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function update(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await register({
        ...form,
        company_name: form.role === 'admin' ? form.company_name : null,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <h1>Create an account</h1>
      <p className="meta" style={{ marginBottom: '1.25rem' }}>
        Pick the role you want to use. This cannot be changed later.
      </p>

      <div className="card">
        <form onSubmit={submit}>
          <Alert kind="error">{error}</Alert>

          <div className="field">
            <label htmlFor="role">I am a…</label>
            <select id="role" value={form.role} onChange={(e) => update('role', e.target.value)}>
              <option value="candidate">Candidate — build a profile, search and apply</option>
              <option value="admin">Company Admin — post and manage job listings</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="full_name">Full name</label>
            <input id="full_name" value={form.full_name} onChange={(e) => update('full_name', e.target.value)} required />
          </div>

          {form.role === 'admin' && (
            <div className="field">
              <label htmlFor="company_name">Company name</label>
              <input
                id="company_name"
                value={form.company_name}
                onChange={(e) => update('company_name', e.target.value)}
                placeholder="e.g. MediCore Health"
              />
              <div className="hint">Used as the default company on jobs you post.</div>
            </div>
          )}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={form.email} onChange={(e) => update('email', e.target.value)} required />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => update('password', e.target.value)}
              required
              minLength={6}
            />
            <div className="hint">At least 6 characters.</div>
          </div>

          <button type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </form>
      </div>

      <p className="meta" style={{ textAlign: 'center' }}>
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </div>
  )
}
