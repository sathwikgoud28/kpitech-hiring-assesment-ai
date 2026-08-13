import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Alert, Badge, Empty, Loading, Tag } from '../../components/ui'

export default function JobsList() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const data = await api.listJobs({ limit: 200 })
      // The list endpoint is public, so filter to this admin's own listings.
      setJobs(data.items.filter((job) => job.created_by === user.id))
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function toggleStatus(job) {
    try {
      await api.setJobStatus(job.id, job.status === 'open' ? 'closed' : 'open')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(job) {
    if (!window.confirm(`Delete "${job.title}"? This also removes its applications.`)) return
    try {
      await api.deleteJob(job.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <div className="page-head row-between">
        <div>
          <h1>My job listings</h1>
          <p>Create, edit, open/close and review applicants.</p>
        </div>
        <Link to="/admin/jobs/new">
          <button>+ Post a job</button>
        </Link>
      </div>

      <Alert kind="error">{error}</Alert>

      {loading ? (
        <Loading />
      ) : !jobs.length ? (
        <Empty>
          You have not posted any jobs yet. <Link to="/admin/jobs/new">Post your first one</Link>.
        </Empty>
      ) : (
        jobs.map((job) => (
          <div className="card" key={job.id}>
            <div className="row-between">
              <div>
                <h3 style={{ marginBottom: '.15rem' }}>{job.title}</h3>
                <div className="meta">
                  {job.company_name}
                  {job.domain && <span className="meta-dot">{job.domain}</span>}
                  <span className="meta-dot">{job.location}</span>
                  <span className="meta-dot">{job.work_mode}</span>
                  <span className="meta-dot">{job.experience_level} level</span>
                </div>
              </div>
              <Badge value={job.status} />
            </div>

            <div className="row" style={{ marginTop: '.55rem' }}>
              {job.required_skills.map((skill) => (
                <Tag key={skill}>{skill}</Tag>
              ))}
            </div>

            <div className="row" style={{ marginTop: '.8rem' }}>
              <Link to={`/admin/jobs/${job.id}/applicants`}>
                <button className="secondary small">View applicants</button>
              </Link>
              <Link to={`/admin/jobs/${job.id}/edit`}>
                <button className="secondary small">Edit</button>
              </Link>
              <button className="secondary small" onClick={() => toggleStatus(job)}>
                {job.status === 'open' ? 'Close listing' : 'Reopen listing'}
              </button>
              <button className="danger small" onClick={() => remove(job)}>
                Delete
              </button>
            </div>
          </div>
        ))
      )}
    </>
  )
}
