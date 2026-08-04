<script>
/**
 * Self-registration, trekkers only. The server gives every account created here
 * the "user" role; admin pre-exists and staff are created by the admin, so
 * neither can be registered from this page.
 */
import { api } from '@/api'

export default {
  name: 'RegisterView',
  data() {
    return {
      form: { full_name: '', email: '', phone: '', password: '' },
      confirm: '',
      error: '',
      success: '',
      busy: false,
    }
  },
  methods: {
    async submit() {
      this.error = ''
      this.success = ''

      // JS validation for the one rule HTML5 attributes cannot express:
      // two fields having to match.
      if (this.form.password !== this.confirm) {
        this.error = 'The two passwords do not match.'
        return
      }

      this.busy = true
      try {
        await api.register(this.form)
        this.success = 'Account created. You can log in now.'
        // Give the message a moment to be read, then move to the login view.
        setTimeout(() => this.$router.push({ name: 'login' }), 1200)
      } catch (e) {
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
    <div class="col-md-6">
      <h1 class="h3 mb-3">Register as a trekker</h1>

      <div v-if="error" class="alert alert-danger">{{ error }}</div>
      <div v-if="success" class="alert alert-success">{{ success }}</div>

      <form @submit.prevent="submit" class="card card-body">
        <div class="mb-3">
          <label class="form-label" for="name">Full name</label>
          <input
            id="name"
            v-model.trim="form.full_name"
            class="form-control"
            required
            maxlength="120"
          />
        </div>

        <div class="mb-3">
          <label class="form-label" for="remail">Email</label>
          <input id="remail" v-model.trim="form.email" type="email" class="form-control" required />
        </div>

        <div class="mb-3">
          <label class="form-label" for="phone">Phone</label>
          <!-- pattern is HTML5 validation: exactly 10 digits. -->
          <input
            id="phone"
            v-model.trim="form.phone"
            class="form-control"
            required
            pattern="[0-9]{10}"
            title="10 digits"
          />
          <div class="form-text">10 digits, no spaces.</div>
        </div>

        <div class="mb-3">
          <label class="form-label" for="rpassword">Password</label>
          <input
            id="rpassword"
            v-model="form.password"
            type="password"
            class="form-control"
            required
            minlength="8"
          />
          <div class="form-text">At least 8 characters.</div>
        </div>

        <div class="mb-3">
          <label class="form-label" for="confirm">Confirm password</label>
          <input
            id="confirm"
            v-model="confirm"
            type="password"
            class="form-control"
            required
            minlength="8"
          />
        </div>

        <button class="btn btn-success w-100" :disabled="busy">
          {{ busy ? 'Creating...' : 'Register' }}
        </button>
      </form>

      <p class="mt-3 text-center">
        Already registered? <router-link to="/login">Login</router-link>
      </p>
    </div>
  </div>
</template>
