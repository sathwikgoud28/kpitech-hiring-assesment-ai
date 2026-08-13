import { useEffect, useState } from 'react'
import { api } from '../../api'
import { Alert, Loading, TagInput } from '../../components/ui'

const EMPTY_EDUCATION = { degree: '', institution: '', year: '' }
const EMPTY_PROJECT = { title: '', summary: '', tech: [] }

export default function Profile() {
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .getMyProfile()
      .then((profile) =>
        setForm({
          full_name: profile.full_name || '',
          headline: profile.headline || '',
          skills: profile.skills || [],
          education: profile.education?.length ? profile.education : [{ ...EMPTY_EDUCATION }],
          projects: profile.projects?.length ? profile.projects : [{ ...EMPTY_PROJECT }],
          years_experience: profile.years_experience ?? 0,
          preferred_location: profile.preferred_location || '',
          preferred_role_type: profile.preferred_role_type || '',
          domain_interests: profile.domain_interests || [],
          work_mode_preference: profile.work_mode_preference || '',
        }),
      )
      .catch((err) => setError(err.message))
  }, [])

  function update(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }))
    setSaved('')
  }

  function updateItem(field, index, key, value) {
    setForm((previous) => {
      const list = [...previous[field]]
      list[index] = { ...list[index], [key]: value }
      return { ...previous, [field]: list }
    })
    setSaved('')
  }

  function addItem(field, blank) {
    setForm((previous) => ({ ...previous, [field]: [...previous[field], { ...blank }] }))
  }

  function removeItem(field, index) {
    setForm((previous) => ({ ...previous, [field]: previous[field].filter((_, i) => i !== index) }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setSaved('')
    try {
      // Strip the blank rows the form starts with so we never persist empties.
      const payload = {
        ...form,
        years_experience: Number(form.years_experience) || 0,
        work_mode_preference: form.work_mode_preference || null,
        preferred_location: form.preferred_location || null,
        preferred_role_type: form.preferred_role_type || null,
        headline: form.headline || null,
        education: form.education.filter((item) => item.degree.trim()),
        projects: form.projects.filter((item) => item.title.trim()),
      }
      await api.saveMyProfile(payload)
      setSaved('Profile saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!form) return error ? <Alert kind="error">{error}</Alert> : <Loading />

  return (
    <>
      <div className="page-head">
        <h1>My profile</h1>
        <p>
          This is what gets attached to every application you send — and what the AI matcher blends
          into your search when you ask it to.
        </p>
      </div>

      <form onSubmit={submit}>
        <Alert kind="error">{error}</Alert>
        <Alert kind="success">{saved}</Alert>

        <div className="card">
          <h2>Basics</h2>
          <div className="grid grid-2">
            <div className="field">
              <label htmlFor="full_name">Full name</label>
              <input id="full_name" value={form.full_name} onChange={(e) => update('full_name', e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="years_experience">Years of experience</label>
              <input
                id="years_experience"
                type="number"
                min="0"
                max="60"
                step="0.5"
                value={form.years_experience}
                onChange={(e) => update('years_experience', e.target.value)}
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="headline">Headline</label>
            <input
              id="headline"
              value={form.headline}
              onChange={(e) => update('headline', e.target.value)}
              placeholder="e.g. Backend engineer, 3 years in Python + FastAPI"
            />
          </div>
          <div className="field">
            <label>Skills</label>
            <TagInput value={form.skills} onChange={(value) => update('skills', value)} placeholder="Type a skill and press Enter" />
            <div className="hint">These drive the skills-overlap signal in AI matching.</div>
          </div>
        </div>

        <div className="card">
          <h2>Preferences</h2>
          <div className="grid grid-2">
            <div className="field">
              <label htmlFor="preferred_location">Preferred location</label>
              <input
                id="preferred_location"
                value={form.preferred_location}
                onChange={(e) => update('preferred_location', e.target.value)}
                placeholder="Hyderabad"
              />
            </div>
            <div className="field">
              <label htmlFor="preferred_role_type">Preferred role type</label>
              <input
                id="preferred_role_type"
                value={form.preferred_role_type}
                onChange={(e) => update('preferred_role_type', e.target.value)}
                placeholder="Backend"
              />
            </div>
            <div className="field">
              <label htmlFor="work_mode_preference">Work mode</label>
              <select
                id="work_mode_preference"
                value={form.work_mode_preference}
                onChange={(e) => update('work_mode_preference', e.target.value)}
              >
                <option value="">No preference</option>
                <option value="onsite">Onsite</option>
                <option value="hybrid">Hybrid</option>
                <option value="remote">Remote</option>
              </select>
            </div>
            <div className="field">
              <label>Domain interests</label>
              <TagInput
                value={form.domain_interests}
                onChange={(value) => update('domain_interests', value)}
                placeholder="Healthcare, Fintech…"
              />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="row-between">
            <h2>Education</h2>
            <button type="button" className="secondary small" onClick={() => addItem('education', EMPTY_EDUCATION)}>
              + Add
            </button>
          </div>
          {form.education.map((item, index) => (
            <div className="row" key={index} style={{ marginBottom: '.6rem', alignItems: 'flex-end' }}>
              <div className="field" style={{ marginBottom: 0, flex: 2, minWidth: '180px' }}>
                <label>Degree</label>
                <input value={item.degree} onChange={(e) => updateItem('education', index, 'degree', e.target.value)} />
              </div>
              <div className="field" style={{ marginBottom: 0, flex: 2, minWidth: '160px' }}>
                <label>Institution</label>
                <input value={item.institution} onChange={(e) => updateItem('education', index, 'institution', e.target.value)} />
              </div>
              <div className="field" style={{ marginBottom: 0, flex: 1, minWidth: '90px' }}>
                <label>Year</label>
                <input value={item.year} onChange={(e) => updateItem('education', index, 'year', e.target.value)} />
              </div>
              <button type="button" className="danger small" onClick={() => removeItem('education', index)}>
                Remove
              </button>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="row-between">
            <h2>Projects</h2>
            <button type="button" className="secondary small" onClick={() => addItem('projects', EMPTY_PROJECT)}>
              + Add
            </button>
          </div>
          {form.projects.map((item, index) => (
            <div key={index} style={{ marginBottom: '1rem', paddingBottom: '.8rem', borderBottom: '1px dashed var(--border)' }}>
              <div className="field">
                <label>Title</label>
                <input value={item.title} onChange={(e) => updateItem('projects', index, 'title', e.target.value)} />
              </div>
              <div className="field">
                <label>Summary</label>
                <textarea
                  value={item.summary}
                  onChange={(e) => updateItem('projects', index, 'summary', e.target.value)}
                  style={{ minHeight: '60px' }}
                />
              </div>
              <div className="field">
                <label>Tech used</label>
                <TagInput
                  value={item.tech || []}
                  onChange={(value) => updateItem('projects', index, 'tech', value)}
                  placeholder="Python, FastAPI…"
                />
              </div>
              <button type="button" className="danger small" onClick={() => removeItem('projects', index)}>
                Remove project
              </button>
            </div>
          ))}
        </div>

        <button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
      </form>
    </>
  )
}
