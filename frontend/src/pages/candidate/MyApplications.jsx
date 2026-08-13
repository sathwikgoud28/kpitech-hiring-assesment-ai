import { useEffect, useState } from 'react'
import { api } from '../../api'
import { Alert, Badge, Empty, Loading } from '../../components/ui'

export default function MyApplications() {
  const [applications, setApplications] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      setApplications(await api.myApplications())
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function withdraw(id) {
    if (!window.confirm('Withdraw this application?')) return
    try {
      await api.withdraw(id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>My applications</h1>
        <p>Track where each application sits in the hiring pipeline.</p>
      </div>

      <Alert kind="error">{error}</Alert>

      {loading ? (
        <Loading />
      ) : !applications.length ? (
        <Empty>You have not applied to anything yet.</Empty>
      ) : (
        applications.map((application) => (
          <div className="card" key={application.id}>
            <div className="row-between">
              <div>
                <h3 style={{ marginBottom: '.15rem' }}>{application.job.title}</h3>
                <div className="meta">
                  {application.job.company_name}
                  <span className="meta-dot">{application.job.location}</span>
                  <span className="meta-dot">
                    Applied {new Date(application.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <Badge value={application.status} />
            </div>

            {application.cover_note && (
              <p className="meta" style={{ marginTop: '.5rem', fontStyle: 'italic' }}>
                “{application.cover_note}”
              </p>
            )}

            <div className="row" style={{ marginTop: '.7rem' }}>
              <button className="danger small" onClick={() => withdraw(application.id)}>
                Withdraw
              </button>
            </div>
          </div>
        ))
      )}
    </>
  )
}
