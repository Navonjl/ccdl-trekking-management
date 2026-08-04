<script>
/**
 * Login for all three roles -- there is one user table on the server, so there
 * is one login form here. Where you land afterwards depends on the roles that
 * /api/me reports back.
 */
import { api } from '@/api'
import { store } from '@/store'

export default {
  name: 'LoginView',
  data() {
    return {
      email: '',
      password: '',
      error: '',
      busy: false,
    }
  },
  methods: {
    async submit() {
      this.error = ''
      this.busy = true
      try {
        // Step 1: exchange email + password for the auth token.
        const data = await api.login(this.email, this.password)
        // Flask-Security puts the token here when include_auth_token is set.
        const token = data?.response?.user?.authentication_token
        if (!token) throw new Error('Login succeeded but no auth token was returned.')
        store.setToken(token)

        // Step 2: ask who we are. We need the roles array to pick a dashboard,
        // and the login response does not necessarily include it.
        const user = await api.me()
        store.setUser(user)

        // Step 3: hand control to the right dashboard component.
        this.$router.push(store.homePath())
      } catch (e) {
        store.logout() // do not keep a half-finished login
        this.error = e.message
      } finally {
        this.busy = false
      }
    },
  },
}
</script>

<template>
  <div class="row justify-content-center">
    <div class="col-md-5">
      <h1 class="h3 mb-1">Trekking Management</h1>
      <p class="text-muted">Sign in to continue.</p>

      <div v-if="error" class="alert alert-danger">{{ error }}</div>

      <!-- No novalidate attribute, so the browser runs HTML5 validation
           (required / type=email) and blocks submit until the form is valid. -->
      <form @submit.prevent="submit" class="card card-body">
        <div class="mb-3">
          <label class="form-label" for="email">Email</label>
          <input
            id="email"
            v-model.trim="email"
            type="email"
            class="form-control"
            required
            autocomplete="username"
          />
        </div>

        <div class="mb-3">
          <label class="form-label" for="password">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            class="form-control"
            required
            autocomplete="current-password"
          />
        </div>

        <button class="btn btn-success w-100" :disabled="busy">
          {{ busy ? 'Signing in...' : 'Login' }}
        </button>
      </form>

      <p class="mt-3 text-center">
        New trekker? <router-link to="/register">Create an account</router-link>
      </p>
    </div>
  </div>
</template>
