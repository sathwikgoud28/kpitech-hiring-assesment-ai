import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Alert, Loading, TagInput } from '../../components/ui'

/** One component serves both "post a job" and "edit a job" - the presence of
 *  :jobId in the route decides which. */
export default function JobForm() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const editing = Boolean(jobId)

  const [form, setForm] = useState({
    title: '',
    description: '',
    required_skills: [],
    experience_level: 'mid',
    location: '',
    status: 'open',
    company_name: user.company_name || '',
    domain: '',
    work_mode: 'onsite',
    company_stage: 'midsize',
    min_years_experience: 0,
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(editing)

  useEffect(() => {
    if (!editing) return
    api
      .getJob(jobId)
      .then((job) =>
        setForm({
          title: job.title,
          description: job.description,
          required_skills: job.required_skills,
          experience_level: job.experience_level,
          location: job.location,
          status: job.status,
          company_name: job.company_name,
          domain: job.domain,
          work_mode: job.work_mode,
          company_stage: job.company_stage,
          min_years_experience: job.min_years_experience,
        }),
      )
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [jobId, editing])

  function update(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = { ...form, min_years_experience: Number(form.min_years_experience) || 0 }
      if (editing) await api.updateJob(jobId, payload)
      else await api.createJob(payload)
      navigate('/admin/jobs')
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  if (loading) return <Loading />

  return (
    <>
      <div className="page-head">
        <h1>{editing ? 'Edit job listing' : 'Post a job'}</h1>
        <p>
          Domain and company stage are optional, but filling them in makes the AI matcher noticeably
          better at ranking this listing.
        </p>
      </div>

      <form onSubmit={submit}>
        <Alert kind="error">{error}</Alert>

        <div className="card">
          <div className="field">
            <label htmlFor="title">Job title</label>
            <input id="title" value={form.title} onChange={(e) => update('title', e.target.value)} required />
          </div>

          <div className="field">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              value={form.description}
              onChange={(e) => update('description', e.target.value)}
              required
              style={{ minHeight: '150px' }}
            />
            <div className="hint">Full text is indexed for the description-similarity signal.</div>
          </div>

          <div className="field">
            <label>Required skills</label>
            <TagInput
              value={form.required_skills}
              onChange={(value) => update('required_skills', value)}
              placeholder="Type a skill and press Enter"
            />
          </div>
        </div>

        <div className="card">
          <h2>Details</h2>
          <div className="grid grid-2">
            <div className="field">
              <label htmlFor="company_name">Company</label>
              <input id="company_name" value={form.company_name} onChange={(e) => update('company_name', e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="domain">Domain</label>
              <input
                id="domain"
                value={form.domain}
                onChange={(e) => update('domain', e.target.value)}
                placeholder="Healthcare, Fintech, E-commerce…"
              />
            </div>
            <div className="field">
              <label htmlFor="location">Location</label>
              <input id="location" value={form.location} onChange={(e) => update('location', e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="work_mode">Work mode</label>
              <select id="work_mode" value={form.work_mode} onChange={(e) => update('work_mode', e.target.value)}>
                <option value="onsite">Onsite</option>
                <option value="hybrid">Hybrid</option>
                <option value="remote">Remote</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="experience_level">Experience level</label>
              <select
                id="experience_level"
                value={form.experience_level}
                onChange={(e) => update('experience_level', e.target.value)}
              >
                <option value="entry">Entry</option>
                <option value="mid">Mid</option>
                <option value="senior">Senior</option>
                <option value="lead">Lead</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="min_years_experience">Minimum years of experience</label>
              <input
                id="min_years_experience"
                type="number"
                min="0"
                max="40"
                step="0.5"
                value={form.min_years_experience}
                onChange={(e) => update('min_years_experience', e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="company_stage">Company stage</label>
              <select id="company_stage" value={form.company_stage} onChange={(e) => update('company_stage', e.target.value)}>
                <option value="startup">Startup</option>
                <option value="midsize">Mid-size</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="status">Status</label>
              <select id="status" value={form.status} onChange={(e) => update('status', e.target.value)}>
                <option value="open">Open — accepting applications</option>
                <option value="closed">Closed</option>
              </select>
              <div className="hint">Only open listings appear in AI matching.</div>
            </div>
          </div>
        </div>

        <div className="row">
          <button type="submit" disabled={busy}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Post job'}
          </button>
          <button type="button" className="secondary" onClick={() => navigate('/admin/jobs')}>
            Cancel
          </button>
        </div>
      </form>
    </>
  )
}
