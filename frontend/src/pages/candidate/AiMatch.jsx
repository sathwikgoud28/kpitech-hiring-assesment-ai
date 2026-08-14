import { useState } from 'react'
import { api } from '../../api'
import JobDetails from '../../components/JobDetails'
import { Alert, Empty, Loading, Tag, scoreClass } from '../../components/ui'

const EXAMPLES = [
  'I want a Python backend role in a startup that does healthcare',
  'Remote React and TypeScript work at a fintech company',
  'Entry-level Python job in Chennai, I just graduated',
  'Senior DevOps role — Kubernetes, Terraform, AWS, fully remote',
  'Machine learning and NLP, ideally something with LLMs',
]

const SIGNAL_LABELS = {
  semantic: 'Description similarity',
  skills: 'Skills overlap',
  role_type: 'Role type',
  domain: 'Domain',
  location: 'Location / mode',
  experience: 'Seniority',
  company_stage: 'Company stage',
}

export default function AiMatch() {
  const [query, setQuery] = useState('')
  const [useProfile, setUseProfile] = useState(true)
  const [useLlm, setUseLlm] = useState(true)
  const [response, setResponse] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [applying, setApplying] = useState(null)
  const [applied, setApplied] = useState({})

  async function runMatch(text, llmOverride) {
    const value = (text ?? query).trim()
    if (value.length < 3) {
      setError('Describe what you are looking for in a few more words.')
      return
    }
    setError('')
    setBusy(true)
    try {
      const data = await api.match({
        query: value,
        limit: 10,
        use_profile: useProfile,
        use_llm: llmOverride ?? useLlm,
      })
      setResponse(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function pickExample(text) {
    setQuery(text)
    runMatch(text)
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

  const parsed = response?.parsed
  const parsedChips = parsed
    ? [
        ...parsed.skills.map((v) => ['Skill', v]),
        ...parsed.role_types.map((v) => ['Role', v]),
        ...parsed.domains.map((v) => ['Domain', v]),
        ...parsed.locations.map((v) => ['Location', v]),
        ...parsed.work_modes.map((v) => ['Mode', v]),
        ...parsed.company_stages.map((v) => ['Stage', v]),
        ...parsed.experience_levels.map((v) => ['Level', v]),
      ]
    : []

  return (
    <>
      <div className="page-head">
        <h1>AI job matching</h1>
        <p>
          Describe the role you want in plain English. Every open listing is scored on seven
          signals and ranked, with the reasoning shown for each result.
        </p>
      </div>

      <div className="card">
        <div className="field">
          <label htmlFor="query">What are you looking for?</label>
          <textarea
            id="query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. I want a Python backend role in a startup that does healthcare"
            onKeyDown={(event) => {
              if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) runMatch()
            }}
          />
          <div className="hint">Ctrl/Cmd + Enter to search.</div>
        </div>

        <div className="row">
          <button onClick={() => runMatch()} disabled={busy}>
            {busy ? 'Matching…' : 'Find matching jobs'}
          </button>
          <label style={{ display: 'flex', alignItems: 'center', gap: '.4rem', margin: 0, fontWeight: 500 }}>
            <input
              type="checkbox"
              checked={useProfile}
              onChange={(event) => setUseProfile(event.target.checked)}
              style={{ width: 'auto' }}
            />
            Blend in my saved profile
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '.4rem', margin: 0, fontWeight: 500 }}>
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(event) => setUseLlm(event.target.checked)}
              style={{ width: 'auto' }}
            />
            Use LLM re-ranking
          </label>
        </div>

        <div style={{ marginTop: '.9rem' }}>
          <div className="hint" style={{ marginBottom: '.35rem' }}>Try one of these:</div>
          <div className="row">
            {EXAMPLES.map((example) => (
              <button key={example} className="secondary small" onClick={() => pickExample(example)}>
                {example}
              </button>
            ))}
          </div>
        </div>
      </div>

      <Alert kind="error">{error}</Alert>

      {busy && <Loading label="Scoring open listings…" />}

      {response && !busy && (
        <>
          <div className="card card-tight">
            <div className="row-between">
              <div>
                <strong>What the system understood</strong>
                <div className="row" style={{ marginTop: '.4rem' }}>
                  {parsedChips.length ? (
                    parsedChips.map(([kind, value]) => (
                      <Tag key={`${kind}-${value}`}>
                        {kind}: {value}
                      </Tag>
                    ))
                  ) : (
                    <span className="meta">
                      Nothing structured was recognised — results fall back to description similarity alone.
                    </span>
                  )}
                </div>
              </div>
              <div className="meta" style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                {response.results.length} of {response.total_open_jobs} open jobs
                <br />
                {response.used_profile ? 'Profile blended in' : 'Query only'}
              </div>
            </div>

            <div className="row" style={{ marginTop: '.7rem', paddingTop: '.7rem', borderTop: '1px dashed var(--border)' }}>
              <span className={`badge ${response.llm_used ? 'badge-shortlisted' : 'badge-neutral'}`}>
                {response.llm_used ? 'Two-stage: engine + LLM' : 'Stage 1 only: deterministic engine'}
              </span>
              <span className="meta">
                {response.llm_used ? (
                  <>
                    Top {Math.min(8, response.results.length)} re-ranked and re-explained by{' '}
                    <strong>{response.llm_model}</strong>. Scores blend both stages 50/50.
                  </>
                ) : response.llm_available ? (
                  'LLM layer is configured but was not used for this search.'
                ) : (
                  'No LLM key configured — running fully offline on the deterministic engine.'
                )}
              </span>
              <button
                className="secondary small"
                style={{ marginLeft: 'auto' }}
                disabled={busy}
                onClick={() => runMatch(response.query, !response.llm_used)}
              >
                {response.llm_used ? 'Re-run without LLM' : 'Re-run with LLM'}
              </button>
            </div>
          </div>

          {response.results.length === 0 && (
            <Empty>Nothing matched that description. Try describing the role differently.</Empty>
          )}

          {response.results.map((result) => (
            <div className="card" key={result.job.id}>
              <div className="row-between">
                <div style={{ flex: 1 }}>
                  <JobDetails job={result.job} matchedSkills={result.matched_skills} />
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className={`score-pill ${scoreClass(result.score)}`}>{Math.round(result.score)}%</div>
                  {result.engine_score != null && (
                    <div className="meta" style={{ fontSize: '.72rem', marginTop: '.3rem', whiteSpace: 'nowrap' }}>
                      engine {Math.round(result.engine_score)} · LLM {Math.round(result.llm_relevance)}
                    </div>
                  )}
                </div>
              </div>

              <p style={{ marginTop: '.75rem', marginBottom: 0, fontWeight: 600, fontSize: '.9rem' }}>
                {result.explanation}
              </p>

              <ul className="reasons">
                {result.reasons.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
              </ul>

              <div className="breakdown">
                {Object.entries(result.breakdown).map(([signal, value]) => (
                  <div className="breakdown-item" key={signal}>
                    <div className="breakdown-label">
                      <span>{SIGNAL_LABELS[signal] || signal}</span>
                      <span>{value === 0 ? '—' : Math.round(value * 100)}</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${value * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              <div className="row" style={{ marginTop: '.9rem' }}>
                <button
                  className="small"
                  onClick={() => apply(result.job.id)}
                  disabled={applying === result.job.id || applied[result.job.id] === 'Applied.'}
                >
                  {applied[result.job.id] === 'Applied.' ? 'Applied ✓' : applying === result.job.id ? 'Applying…' : 'Apply'}
                </button>
                {applied[result.job.id] && applied[result.job.id] !== 'Applied.' && (
                  <span className="meta" style={{ color: 'var(--red)' }}>{applied[result.job.id]}</span>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  )
}
