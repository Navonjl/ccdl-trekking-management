/**
 * Every call to the Flask API goes through this file. Nothing else in the app
 * calls fetch(), so there is exactly one place that knows about URLs, the auth
 * header and the error format.
 *
 * Endpoints used (all served by Flask on port 5000, reached through the Vite
 * proxy configured in vite.config.js):
 *
 *   auth      POST   /api/accounts/login?include_auth_token
 *             POST   /api/accounts/logout
 *             POST   /api/register
 *             GET    /api/me
 *             PUT    /api/profile
 *   trekker   GET    /api/treks?q&difficulty&location&min_days&max_days
 *             GET    /api/bookings
 *             POST   /api/bookings                        {trek_id}
 *             POST   /api/bookings/<id>/cancel
 *   exports   POST   /api/exports/bookings
 *             GET    /api/exports/<task_id>
 *             GET    /api/exports/download/<filename>
 *   admin     GET    /api/admin/stats
 *             GET    /api/admin/treks?q
 *             POST   /api/admin/treks    PUT/DELETE /api/admin/treks/<id>
 *             PUT    /api/admin/treks/<id>/assign-staff   {staff_id}
 *             GET    /api/admin/staff?q   POST /api/admin/staff
 *             GET    /api/admin/users?q
 *             POST   /api/admin/users/<id>/deactivate | reactivate
 *             POST   /api/admin/users/<id>/blacklist  | unblacklist
 *             GET    /api/admin/bookings?status&trek_id
 *   staff     GET    /api/staff/dashboard
 *             PUT    /api/staff/treks/<id>                {available_slots, status}
 *             GET    /api/staff/treks/<id>/participants
 */
import { store } from './store'

/* ------------------------------------------------------------------ helpers */

/**
 * Turn a failed response into one readable sentence.
 *
 * Two different error shapes reach us, which is why this is not a one-liner:
 * our own blueprints answer {"error": "..."} (see app/api/__init__.py) while
 * Flask-Security answers {"response": {"errors": [...], "field_errors": {...}}}.
 */
function errorMessage(data, status) {
  if (typeof data.error === 'string') return data.error

  const r = data.response || {}

  if (Array.isArray(r.errors) && r.errors.length) {
    return r.errors.map((e) => (typeof e === 'string' ? e : e.message || String(e))).join(' ')
  }
  if (r.field_errors && typeof r.field_errors === 'object') {
    const messages = Object.values(r.field_errors).flat()
    if (messages.length) return messages.join(' ')
  }
  if (typeof data.message === 'string') return data.message

  if (status === 401) return 'Please log in again.'
  if (status === 403) return 'You are not allowed to do that.'
  return `Request failed (HTTP ${status}).`
}

/**
 * The single fetch wrapper. Adds the auth header, parses JSON, and throws an
 * Error with a display-ready message when the server says no, so that every
 * caller can just use try/catch.
 */
async function request(path, { method = 'GET', body = null } = {}) {
  // The Accept header matters more than it looks: without it, Flask-Security
  // answers an unauthenticated request with a 302 redirect to its HTML login
  // page, fetch() follows the redirect, and we would see a "successful" HTML
  // response instead of an error. Asking for JSON makes it answer 401 + JSON.
  const options = { method, headers: { Accept: 'application/json' } }

  if (body !== null) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  // This header is how Flask-Security recognises us on every request after
  // login (config.py sets SECURITY_API_ENABLED_METHODS = ["session", "token"]).
  if (store.token) options.headers['Authentication-Token'] = store.token

  const response = await fetch('/api' + path, options)

  // A 204 has no body, and a Flask crash page is HTML rather than JSON, so
  // parse defensively instead of calling response.json() directly.
  const text = await response.text()
  let data = {}
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = {}
    }
  }

  if (!response.ok) {
    // A rejected token means the session is over; drop it so the router guard
    // sends the user back to the login page on the next navigation.
    if (response.status === 401) store.logout()
    throw new Error(errorMessage(data, response.status))
  }
  return data
}

/**
 * List endpoints may answer either a bare array or an object wrapping one
 * (e.g. {"treks": [...]}). Normalising here keeps every view's code identical:
 * they always receive a plain array.
 */
function asList(data, ...keys) {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object') {
    for (const key of keys) {
      if (Array.isArray(data[key])) return data[key]
    }
    // Fall back to the first array-valued property, whatever it is called.
    const firstArray = Object.values(data).find((v) => Array.isArray(v))
    if (firstArray) return firstArray
  }
  return []
}

/** Build "?a=1&b=2", skipping empty filter boxes so we do not send q=. */
function queryString(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== '' && value !== null && value !== undefined) search.set(key, value)
  }
  const s = search.toString()
  return s ? '?' + s : ''
}

/**
 * Dig the auth token out of the login response.
 *
 * Flask-Security 5.x returns {"response": {"user": {"authentication_token": ...}}},
 * but older/other configurations nest it differently, so read whichever of the
 * known positions actually holds a string rather than assuming one shape.
 */
export function extractToken(data) {
  const candidates = [
    data?.response?.user?.authentication_token,
    data?.response?.authentication_token,
    data?.user?.authentication_token,
    data?.authentication_token,
  ]
  return candidates.find((t) => typeof t === 'string' && t.length > 0) || ''
}

/* ------------------------------------------------------------- the API calls */

export const api = {
  /* ---- authentication ---- */

  // include_auth_token is required: without it Flask-Security does NOT put the
  // token in the response body (it assumes a cookie session instead).
  login(email, password) {
    return request('/accounts/login?include_auth_token', {
      method: 'POST',
      body: { email, password },
    })
  },

  logout() {
    return request('/accounts/logout', { method: 'POST' })
  },

  register(payload) {
    return request('/register', { method: 'POST', body: payload })
  },

  /** The logged-in user, including the roles array the router guard needs. */
  async me() {
    const data = await request('/me')
    // Accept either the user object directly or {"user": {...}}.
    return data.user || data
  },

  updateProfile(payload) {
    return request('/profile', { method: 'PUT', body: payload })
  },

  /* ---- trekker: browsing and booking ---- */

  async treks(filters) {
    return asList(await request('/treks' + queryString(filters)), 'treks', 'items')
  },

  async bookings() {
    return asList(await request('/bookings'), 'bookings', 'items')
  },

  bookTrek(trekId) {
    return request('/bookings', { method: 'POST', body: { trek_id: trekId } })
  },

  // Cancelling sets the status rather than deleting the row (the spec wants a
  // complete history), which is why it is its own POST action and not a DELETE.
  cancelBooking(bookingId) {
    return request('/bookings/' + bookingId + '/cancel', { method: 'POST' })
  },

  /* ---- trekker: CSV export (Celery job) ---- */

  startExport() {
    return request('/exports/bookings', { method: 'POST' })
  },

  exportStatus(taskId) {
    return request('/exports/' + taskId)
  },

  /**
   * Download the finished CSV.
   *
   * This cannot be a plain <a href> link: the download route is behind token
   * auth and an anchor cannot send the Authentication-Token header. So fetch the
   * file with the header, then hand the browser a temporary blob: URL to save.
   */
  async downloadExport(filename) {
    const response = await fetch('/api/exports/download/' + encodeURIComponent(filename), {
      headers: store.token ? { 'Authentication-Token': store.token } : {},
    })
    if (!response.ok) throw new Error(`Could not download the file (HTTP ${response.status}).`)

    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  },

  /* ---- admin ---- */

  stats() {
    return request('/admin/stats')
  },

  async adminTreks(q) {
    return asList(await request('/admin/treks' + queryString({ q })), 'treks', 'items')
  },

  createTrek(payload) {
    return request('/admin/treks', { method: 'POST', body: payload })
  },

  updateTrek(id, payload) {
    return request('/admin/treks/' + id, { method: 'PUT', body: payload })
  },

  deleteTrek(id) {
    return request('/admin/treks/' + id, { method: 'DELETE' })
  },

  /**
   * Assigning staff is a separate endpoint, not a field on the trek: the server
   * checks that the staff member exists and is still active before accepting it.
   * Pass null to remove the assignment.
   */
  assignStaff(trekId, staffId) {
    return request('/admin/treks/' + trekId + '/assign-staff', {
      method: 'PUT',
      body: { staff_id: staffId },
    })
  },

  async adminStaff(q) {
    return asList(await request('/admin/staff' + queryString({ q })), 'staff', 'items')
  },

  createStaff(payload) {
    return request('/admin/staff', { method: 'POST', body: payload })
  },

  async adminUsers(q) {
    return asList(await request('/admin/users' + queryString({ q })), 'users', 'items')
  },

  /**
   * Deactivate/blacklist are four separate POST actions rather than a PUT with a
   * flag, and they take a USER id. Staff are rows in the same user table, so the
   * staff page uses these too (passing the staff member's user_id).
   *
   * `action` is one of: deactivate, reactivate, blacklist, unblacklist.
   */
  userAction(userId, action) {
    return request('/admin/users/' + userId + '/' + action, { method: 'POST' })
  },

  async adminBookings(filters) {
    return asList(await request('/admin/bookings' + queryString(filters)), 'bookings', 'items')
  },

  /* ---- staff ---- */

  // The server wraps the list: {staff: {...}, assigned_treks: [...], total_assigned: n}.
  async staffDashboard() {
    return asList(await request('/staff/dashboard'), 'assigned_treks', 'treks')
  },

  /** Staff may change only the slots and the status of a trek assigned to them. */
  updateStaffTrek(id, payload) {
    return request('/staff/treks/' + id, { method: 'PUT', body: payload })
  },

  async participants(trekId) {
    return asList(
      await request('/staff/treks/' + trekId + '/participants'),
      'participants',
      'bookings',
      'items',
    )
  },
}
