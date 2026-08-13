/**
 * Thin fetch wrapper around the backend API.
 *
 * Everything goes through `request()` so token attachment and error unwrapping
 * live in exactly one place. The backend always returns errors as
 * `{"detail": "..."}`, so the UI can render `err.message` directly.
 */

const TOKEN_KEY = 'jobboard.token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 204) return null

  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const message = payload?.detail || `Request failed (${response.status})`
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  return payload
}

function query(params) {
  const search = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.append(key, value)
    }
  })
  const string = search.toString()
  return string ? `?${string}` : ''
}

export const api = {
  // --- auth ---------------------------------------------------------------
  register: (payload) => request('/auth/register', { method: 'POST', body: payload, auth: false }),
  login: (payload) => request('/auth/login', { method: 'POST', body: payload, auth: false }),
  me: () => request('/auth/me'),

  // --- jobs ---------------------------------------------------------------
  listJobs: (filters) => request(`/jobs${query(filters)}`),
  getJob: (id) => request(`/jobs/${id}`),
  createJob: (payload) => request('/jobs', { method: 'POST', body: payload }),
  updateJob: (id, payload) => request(`/jobs/${id}`, { method: 'PUT', body: payload }),
  setJobStatus: (id, status) =>
    request(`/jobs/${id}/status${query({ new_status: status })}`, { method: 'PATCH' }),
  deleteJob: (id) => request(`/jobs/${id}`, { method: 'DELETE' }),

  // --- candidate profile --------------------------------------------------
  getMyProfile: () => request('/candidates/me/profile'),
  saveMyProfile: (payload) => request('/candidates/me/profile', { method: 'PUT', body: payload }),

  // --- applications -------------------------------------------------------
  apply: (payload) => request('/applications', { method: 'POST', body: payload }),
  myApplications: () => request('/applications/me'),
  applicationsForJob: (jobId, status) =>
    request(`/applications/job/${jobId}${query({ status })}`),
  setApplicationStatus: (id, status) =>
    request(`/applications/${id}/status`, { method: 'PATCH', body: { status } }),
  withdraw: (id) => request(`/applications/${id}`, { method: 'DELETE' }),

  // --- ai matching --------------------------------------------------------
  match: (payload) => request('/match', { method: 'POST', body: payload }),

  // --- dashboard ----------------------------------------------------------
  dashboard: () => request('/dashboard'),
}
