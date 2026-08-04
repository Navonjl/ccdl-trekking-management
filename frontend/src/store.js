/**
 * The one piece of shared state in the app: who is logged in.
 *
 * This is deliberately NOT Vuex/Pinia. All we need to share between components
 * is the auth token and the logged-in user, so a single reactive() object is
 * enough. Any component that imports `store` sees the same object, and because
 * it is reactive, templates re-render when it changes.
 *
 * The token and user are also copied into localStorage so a page refresh (F5)
 * does not log you out.
 */
import { reactive } from 'vue'

const TOKEN_KEY = 'tma_token'
const USER_KEY = 'tma_user'

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY)) || null
  } catch {
    // Corrupt/hand-edited localStorage should not crash the whole app.
    return null
  }
}

export const store = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: loadUser(),

  setToken(token) {
    this.token = token || ''
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  },

  setUser(user) {
    this.user = user || null
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  },

  logout() {
    this.setToken('')
    this.setUser(null)
  },

  /** True when the logged-in user holds this role name ("admin"/"staff"/"user"). */
  hasRole(name) {
    return !!this.user && Array.isArray(this.user.roles) && this.user.roles.includes(name)
  },

  /**
   * Where a user belongs after logging in. Admin wins over staff, staff over
   * trekker, so an account holding two roles still lands somewhere sensible.
   */
  homePath() {
    if (this.hasRole('admin')) return '/admin'
    if (this.hasRole('staff')) return '/staff'
    return '/treks'
  },
})
