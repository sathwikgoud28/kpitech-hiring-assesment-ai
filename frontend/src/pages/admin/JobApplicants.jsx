import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api'
import { Alert, Badge, Empty, Loading, Tag } from '../../components/ui'

const PIPELINE = ['applied', 'shortlisted', 'rejected']

export default function JobApplicants() {
  const { jobId } = useParams()
  const [job, setJob] = useState(null)
  const [applications, setApplications] = useState([])
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})

  async function load(status = filter) {
    setLoading(true)
    try {
      const [jobData, applicationData] = await Promise.all([
        api.getJob(jobId),
        api.applicationsForJob(jobId, status || undefined),
      ])
      setJob(jobData)
      setApplications(applicationData)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  function applyFilter(status) {
    setFilter(status)
    load(status)
  }

  async function setStatus(applicationId, status) {
    try {
      await api.setApplicationStatus(applicationId, status)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading && !job) return <Loading />

  return (
    <>
      <div className="page-head">
        <Link to="/admin/jobs" className="meta">
          ← Back to my job listings
        </Link>
        <h1 style={{ marginTop: '.4rem' }}>Applicants{job ? ` — ${job.title}` : ''}</h1>
        {job && (
          <p className="meta">
            {job.company_name}
            <span className="meta-dot">{job.location}</span>
            <span className="meta-dot">{job.experience_level} level</span>
          </p>
        )}
      </div>

      <Alert kind="error">{error}</Alert>

      <div className="card card-tight">
        <div className="row">
          <strong style={{ fontSize: '.85rem' }}>Filter:</strong>
          <button className={filter ? 'secondary small' : 'small'} onClick={() => applyFilter('')}>
            All
          </button>
          {PIPELINE.map((status) => (
            <button
              key={status}
              className={filter === status ? 'small' : 'secondary small'}
              onClick={() => applyFilter(status)}
              style={{ textTransform: 'capitalize' }}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Loading />
      ) : !applications.length ? (
        <Empty>No applications{filter ? ` with status "${filter}"` : ''} yet.</Empty>
      ) : (
        applications.map((application) => {
          const snapshot = application.profile_snapshot || {}
          const isOpen = expanded[application.id]
          return (
            <div className="card" key={application.id}>
              <div className="row-between">
                <div>
                  <h3 style={{ marginBottom: '.15rem' }}>{application.candidate_name}</h3>
                  <div className="meta">
                    {application.candidate_email}
                    {snapshot.years_experience != null && (
                      <span className="meta-dot">{snapshot.years_experience} yrs experience</span>
                    )}
                    <span className="meta-dot">
                      Applied {new Date(application.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {snapshot.headline && (
                    <div className="meta" style={{ marginTop: '.2rem' }}>{snapshot.headline}</div>
                  )}
                </div>
                <Badge value={application.status} />
              </div>

              <div className="row" style={{ marginTop: '.55rem' }}>
                {(snapshot.skills || []).map((skill) => (
                  <Tag key={skill}>{skill}</Tag>
                ))}
              </div>

              {application.cover_note && (
                <p className="meta" style={{ marginTop: '.6rem', fontStyle: 'italic' }}>
                  “{application.cover_note}”
                </p>
              )}

              <div className="row" style={{ marginTop: '.8rem' }}>
                {PIPELINE.map((status) => (
                  <button
                    key={status}
                    className={application.status === status ? 'small' : 'secondary small'}
                    disabled={application.status === status}
                    onClick={() => setStatus(application.id, status)}
                    style={{ textTransform: 'capitalize' }}
                  >
                    {status === 'applied' ? 'Reset to applied' : status}
                  </button>
                ))}
                <button
                  className="secondary small"
                  onClick={() => setExpanded((p) => ({ ...p, [application.id]: !isOpen }))}
                >
                  {isOpen ? 'Hide full profile' : 'View full profile'}
                </button>
              </div>

              {isOpen && (
                <div style={{ marginTop: '.9rem', paddingTop: '.9rem', borderTop: '1px dashed var(--border)' }}>
                  <div className="grid grid-2">
                    <div>
                      <h3>Education</h3>
                      {(snapshot.education || []).length ? (
                        (snapshot.education || []).map((item, index) => (
                          <div key={index} className="meta" style={{ marginBottom: '.3rem' }}>
                            <strong style={{ color: 'var(--text)' }}>{item.degree}</strong>
                            {item.institution && <> — {item.institution}</>}
                            {item.year && <> ({item.year})</>}
                          </div>
                        ))
                      ) : (
                        <p className="meta">Not provided.</p>
                      )}

                      <h3 style={{ marginTop: '.9rem' }}>Preferences</h3>
                      <div className="meta">
                        Location: {snapshot.preferred_location || '—'}
                        <br />
                        Role type: {snapshot.preferred_role_type || '—'}
                        <br />
                        Work mode: {snapshot.work_mode_preference || '—'}
                        <br />
                        Domains: {(snapshot.domain_interests || []).join(', ') || '—'}
                      </div>
                    </div>

                    <div>
                      <h3>Projects</h3>
                      {(snapshot.projects || []).length ? (
                        (snapshot.projects || []).map((item, index) => (
                          <div key={index} style={{ marginBottom: '.7rem' }}>
                            <strong style={{ fontSize: '.9rem' }}>{item.title}</strong>
                            <p className="meta" style={{ margin: '.15rem 0' }}>{item.summary}</p>
                            <div className="row">
                              {(item.tech || []).map((tech) => (
                                <Tag key={tech}>{tech}</Tag>
                              ))}
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="meta">Not provided.</p>
                      )}
                    </div>
                  </div>
                  <p className="hint" style={{ marginTop: '.7rem' }}>
                    This is a snapshot taken when the candidate applied, not their live profile.
                  </p>
                </div>
              )}
            </div>
          )
        })
      )}
    </>
  )
}
