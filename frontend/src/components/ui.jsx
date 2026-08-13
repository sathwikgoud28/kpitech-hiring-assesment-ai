/** Small presentational building blocks shared across pages. */

const STATUS_CLASS = {
  open: 'badge-open',
  closed: 'badge-closed',
  applied: 'badge-applied',
  shortlisted: 'badge-shortlisted',
  rejected: 'badge-rejected',
}

export function Badge({ value }) {
  return <span className={`badge ${STATUS_CLASS[value] || 'badge-neutral'}`}>{value}</span>
}

export function Tag({ children, variant, onRemove }) {
  const className = ['tag', variant === 'match' && 'tag-match', variant === 'gap' && 'tag-gap', onRemove && 'tag-removable']
    .filter(Boolean)
    .join(' ')
  return (
    <span className={className} onClick={onRemove} title={onRemove ? 'Click to remove' : undefined}>
      {children}
      {onRemove ? ' ×' : ''}
    </span>
  )
}

export function Alert({ kind = 'info', children }) {
  if (!children) return null
  return <div className={`alert alert-${kind}`}>{children}</div>
}

export function Loading({ label = 'Loading…' }) {
  return <div className="loading">{label}</div>
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function Stat({ label, value }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

/** Horizontal bar chart. Bars are scaled against the largest value present. */
export function BarChart({ data, emptyLabel = 'No data yet.' }) {
  if (!data?.length) return <p className="meta">{emptyLabel}</p>
  const max = Math.max(...data.map((item) => item.value), 1)
  return (
    <div>
      {data.map((item) => (
        <div className="bar-row" key={item.label}>
          <span title={item.label}>{item.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(item.value / max) * 100}%` }} />
          </span>
          <span className="bar-value">{item.value}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * Comma/Enter-separated tag input. Used for skills and domain interests, where
 * a plain comma-separated text box loses items to stray whitespace.
 */
export function TagInput({ value = [], onChange, placeholder }) {
  function commit(event) {
    if (event.key !== 'Enter' && event.key !== ',') return
    event.preventDefault()
    const raw = event.target.value.trim().replace(/,$/, '')
    if (!raw) return
    if (!value.some((item) => item.toLowerCase() === raw.toLowerCase())) {
      onChange([...value, raw])
    }
    event.target.value = ''
  }

  return (
    <div>
      <input type="text" onKeyDown={commit} placeholder={placeholder} />
      <div className="row" style={{ marginTop: '.45rem' }}>
        {value.map((item) => (
          <Tag key={item} onRemove={() => onChange(value.filter((entry) => entry !== item))}>
            {item}
          </Tag>
        ))}
      </div>
    </div>
  )
}

export function scoreClass(score) {
  if (score >= 75) return 'score-strong'
  if (score >= 55) return 'score-good'
  if (score >= 35) return 'score-partial'
  return 'score-weak'
}
