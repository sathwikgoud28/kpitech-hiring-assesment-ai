import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Loading } from './components/ui'
import { useAuth } from './auth'

import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/admin/Dashboard'
import JobsList from './pages/admin/JobsList'
import JobForm from './pages/admin/JobForm'
import JobApplicants from './pages/admin/JobApplicants'
import AiMatch from './pages/candidate/AiMatch'
import BrowseJobs from './pages/candidate/BrowseJobs'
import MyApplications from './pages/candidate/MyApplications'
import Profile from './pages/candidate/Profile'

/**
 * Route table with two role-gated branches.
 *
 * Guarding in the router keeps every page component free of auth checks - a
 * page can assume it would not have rendered if the user were not allowed.
 * The backend enforces the same rules independently; this layer is UX, not
 * security.
 */
export default function App() {
  const { user, loading, isAdmin } = useAuth()

  if (loading) return <Loading label="Starting up…" />

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        {isAdmin ? (
          <>
            <Route path="/admin" element={<Dashboard />} />
            <Route path="/admin/jobs" element={<JobsList />} />
            <Route path="/admin/jobs/new" element={<JobForm />} />
            <Route path="/admin/jobs/:jobId/edit" element={<JobForm />} />
            <Route path="/admin/jobs/:jobId/applicants" element={<JobApplicants />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </>
        ) : (
          <>
            <Route path="/match" element={<AiMatch />} />
            <Route path="/jobs" element={<BrowseJobs />} />
            <Route path="/applications" element={<MyApplications />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="*" element={<Navigate to="/match" replace />} />
          </>
        )}
      </Route>
    </Routes>
  )
}
