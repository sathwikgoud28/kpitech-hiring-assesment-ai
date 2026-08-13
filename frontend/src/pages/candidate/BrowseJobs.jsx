import { useEffect, useState } from 'react'
import { api } from '../../api'
import JobDetails from '../../components/JobDetails'
import { Alert, Empty, Loading } from '../../components/ui'

const BLANK = { q: '', skills: '', location: '', experience_level: '', work_mode: '' }

export default function BrowseJobs() {
  const [filters, setFilters] = useState(BLANK)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState(null)
  const [applied, setApplied] = useState({})

  async function load(active = filters) {
    setLoading(true)
    setError('')
    try {
      // Candidates only ever browse open listings.
      setData(await api.listJobs({ ...active, status: 'open' }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(BLANK)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function update(field, value) {
    setFilters((previous) => ({ ...previous, [field]: value }))
  }

  function reset() {
    setFilters(BLANK)
    load(BLANK)
  }

  async function apply(jobId) {
    setApplying(jobId)
    try {
      await api.apply({ job_id: jobId })
      setApplied((previous) => ({ ...previous, [jobId]: 'Applied.' }))
    } catch (err) {
      setApplied((previous) => ({ ...previous, [jobId]: err.message }))
    } finally {
      setApplying(null)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Browse jobs</h1>
        <p>Search and filter every open listing by keyword, skills, location and experience level.</p>
      </div>

      <div className="card">
        <div className="grid grid-2">
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="q">Keyword</label>
            <input
              id="q"
              value={filters.q}
              onChange={(event) => update('q', event.target.value)}
              placeholder="Title, description or company"
              onKeyDown={(event) => event.key === 'Enter' && load()}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="skills">Skills</label>
            <input
              id="skills"
              value={filters.skills}
              onChange={(event) => update('skills', event.target.value)}
              placeholder="Python, React  (matches any)"
              onKeyDown={(event) => event.key === 'Enter' && load()}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="location">Location</label>
            <input
              id="location"
              value={filters.location}
              onChange={(event) => update('location', event.target.value)}
              placeholder="Hyderabad"
              onKeyDown={(event) => event.key === 'Enter' && load()}
            />
          </div>
          <div className="row" style={{ alignItems: 'flex-end' }}>
            <div className="field" style={{ marginBottom: 0, flex: 1 }}>
              <label htmlFor="experience_level">Experience</label>
              <select
                id="experience_level"
                value={filters.experience_level}
                onChange={(event) => update('experience_level', event.target.value)}
              >
                <option value="">Any</option>
                <option value="entry">Entry</option>
                <option value="mid">Mid</option>
                <option value="senior">Senior</option>
                <option value="lead">Lead</option>
              </select>
            </div>
            <div className="field" style={{ marginBottom: 0, flex: 1 }}>
              <label htmlFor="work_mode">Work mode</label>
              <select id="work_mode" value={filters.work_mode} onChange={(event) => update('work_mode', event.target.value)}>
                <option value="">Any</option>
                <option value="onsite">Onsite</option>
                <option value="hybrid">Hybrid</option>
                <option value="remote">Remote</option>
              </select>
            </div>
          </div>
        </div>

        <div className="row" style={{ marginTop: '.9rem' }}>
          <button onClick={() => load()}>Search</button>
          <button className="secondary" onClick={reset}>
            Clear
          </button>
        </div>
      </div>

      <Alert kind="error">{error}</Alert>

      {loading ? (
        <Loading />
      ) : !data?.items.length ? (
        <Empty>No open jobs match those filters.</Empty>
      ) : (
        <>
          <p className="meta">{data.total} open job{data.total === 1 ? '' : 's'}</p>
          {data.items.map((job) => (
            <div className="card" key={job.id}>
              <JobDetails job={job} />
              <div className="row" style={{ marginTop: '.8rem' }}>
                <button
                  className="small"
                  onClick={() => apply(job.id)}
                  disabled={applying === job.id || applied[job.id] === 'Applied.'}
                >
                  {applied[job.id] === 'Applied.' ? 'Applied ✓' : applying === job.id ? 'Applying…' : 'Apply'}
                </button>
                {applied[job.id] && applied[job.id] !== 'Applied.' && (
                  <span className="meta" style={{ color: 'var(--red)' }}>{applied[job.id]}</span>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  )
}
