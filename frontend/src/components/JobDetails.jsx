import { Badge, Tag } from './ui'

/** The job facts shown identically on the browse list and the match results. */
export default function JobDetails({ job, matchedSkills = [], showStatus = false }) {
  const matched = new Set(matchedSkills.map((skill) => skill.toLowerCase()))

  return (
    <>
      <div className="row-between">
        <div>
          <h3 style={{ marginBottom: '.15rem' }}>{job.title}</h3>
          <div className="meta">
            {job.company_name || 'Unnamed company'}
            {job.domain && <span className="meta-dot">{job.domain}</span>}
            <span className="meta-dot">{job.company_stage}</span>
          </div>
        </div>
        {showStatus && <Badge value={job.status} />}
      </div>

      <div className="meta" style={{ marginTop: '.35rem' }}>
        {job.location}
        <span className="meta-dot">{job.work_mode}</span>
        <span className="meta-dot">{job.experience_level} level</span>
        {job.min_years_experience > 0 && <span className="meta-dot">{job.min_years_experience}+ yrs</span>}
      </div>

      <p style={{ margin: '.6rem 0', fontSize: '.9rem' }}>{job.description}</p>

      <div className="row">
        {job.required_skills.map((skill) => (
          <Tag key={skill} variant={matched.has(skill.toLowerCase()) ? 'match' : undefined}>
            {skill}
          </Tag>
        ))}
      </div>
    </>
  )
}
