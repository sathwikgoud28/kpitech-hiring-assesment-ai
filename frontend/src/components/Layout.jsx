import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'

/** App shell: brand, role-appropriate navigation, and the signed-in user. */
export default function Layout() {
  const { user, isAdmin, logout } = useAuth()

  const links = isAdmin
    ? [
        { to: '/admin', label: 'Dashboard', end: true },
        { to: '/admin/jobs', label: 'My Job Listings' },
        { to: '/admin/jobs/new', label: 'Post a Job' },
      ]
    : [
        { to: '/match', label: 'AI Match' },
        { to: '/jobs', label: 'Browse Jobs' },
        { to: '/applications', label: 'My Applications' },
        { to: '/profile', label: 'My Profile' },
      ]

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            KPi<span>·</span>Tech Job Board
          </div>
          <nav className="nav">
            {links.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end}>
                {link.label}
              </NavLink>
            ))}
          </nav>
          <div className="topbar-user">
            <span>
              {user.full_name} · <strong>{isAdmin ? 'Company Admin' : 'Candidate'}</strong>
            </span>
            <button className="secondary small" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
