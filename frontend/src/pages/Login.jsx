import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth'
import { Alert } from '../components/ui'

const DEMO = [
  { label: 'Company Admin (MediCore Health)', email: 'admin@medicore.io' },
  { label: 'Company Admin (FinStack Labs)', email: 'admin@finstack.io' },
  { label: 'Candidate (Python backend, 3 yrs)', email: 'sana.k@example.com' },
  { label: 'Candidate (ML / NLP, 4 yrs)', email: 'rahul.d@example.com' },
]
const DEMO_PASSWORD = 'Password123'

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function useDemo(demoEmail) {
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    setError('')
  }

  return (
    <div className="auth-wrap">
      <h1>KPi-Tech Job Board</h1>
      <p className="meta" style={{ marginBottom: '1.25rem' }}>
        Sign in as a Company Admin or a Candidate.
      </p>

      <div className="card">
        <form onSubmit={submit}>
          <Alert kind="error">{error}</Alert>

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="demo-accounts">
          <strong>Demo accounts</strong> — password <code>{DEMO_PASSWORD}</code>
          {DEMO.map((account) => (
            <div key={account.email}>
              <button className="secondary small" type="button" onClick={() => useDemo(account.email)}>
                {account.label}
              </button>
            </div>
          ))}
        </div>
      </div>

      <p className="meta" style={{ textAlign: 'center' }}>
        No account? <Link to="/register">Create one</Link>
      </p>
    </div>
  )
}
