import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Alert, Badge, BarChart, Empty, Loading, Stat } from '../../components/ui'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboard().then(setData).catch((err) => setError(err.message))
  }, [])

  if (error) return <Alert kind="error">{error}</Alert>
  if (!data) return <Loading />

  const { pipeline } = data
  const pipelineData = [
    { label: 'Applied', value: pipeline.applied },
    { label: 'Shortlisted', value: pipeline.shortlisted },
    { label: 'Rejected', value: pipeline.rejected },
  ]
  const skillData = data.skill_distribution.map((item) => ({ label: item.skill, value: item.count }))

  return (
    <>
      <div className="page-head">
        <h1>Dashboard</h1>
        <p>Applications per job, skill distribution across applicants, and pipeline status counts.</p>
      </div>

      <div className="grid grid-4" style={{ marginBottom: '1rem' }}>
        <Stat label="Job listings" value={data.total_jobs} />
        <Stat label="Open" value={data.open_jobs} />
        <Stat label="Applications" value={data.total_applications} />
        <Stat label="Unique applicants" value={data.total_applicants} />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h2>Pipeline status</h2>
          <BarChart data={pipelineData} emptyLabel="No applications yet." />
        </div>

        <div className="card">
          <h2>Skill distribution across applicants</h2>
          <p className="hint" style={{ marginTop: '-.4rem', marginBottom: '.7rem' }}>
            Counted from the profile snapshot taken when each application was submitted.
          </p>
          <BarChart data={skillData} emptyLabel="No applicants yet." />
        </div>
      </div>

      <div className="card">
        <h2>Applications per job</h2>
        {!data.applications_per_job.length ? (
          <Empty>
            You have not posted any jobs yet. <Link to="/admin/jobs/new">Post one</Link>.
          </Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Status</th>
                <th>Total</th>
                <th>Applied</th>
                <th>Shortlisted</th>
                <th>Rejected</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.applications_per_job.map((row) => (
                <tr key={row.job_id}>
                  <td>{row.job_title}</td>
                  <td>
                    <Badge value={row.status} />
                  </td>
                  <td>
                    <strong>{row.total}</strong>
                  </td>
                  <td>{row.applied}</td>
                  <td>{row.shortlisted}</td>
                  <td>{row.rejected}</td>
                  <td>
                    <Link to={`/admin/jobs/${row.job_id}/applicants`}>View applicants</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
