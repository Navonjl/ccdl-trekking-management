<script>
/**
 * "Edit their profile" for whoever is logged in. Reachable by every role, so the
 * route only requires auth and does not pin a role.
 */
import { api } from '@/api'
import { store } from '@/store'

export default {
  name: 'ProfileView',
  data() {
    return {
      store,
      form: { full_name: '', phone: '' },
      password: '',
      error: '',
      success: '',
      busy: false,
    }
  },
  // Fill the form from the server so it shows current values, not stale ones.
  async created() {
    try {
      const user = await api.me()
      store.setUser(user)
      this.form.full_name = user.full_name || ''
      this.form.phone = user.phone || ''
    } catch (e) {
      this.error = e.message
    }
  },
  methods: {
    async submit() {
      this.error = ''
      this.success = ''
      this.busy = true

      // Only send the password when the user actually typed a new one, so
      // saving the name does not blank out the password.
      const payload = { ...this.form }
      if (this.password) payload.password = this.password

      try {
        await api.updateProfile(payload)
        store.setUser(await api.me()) // refresh the copy the navbar shows
        this.password = ''
        this.success = 'Profile saved.'
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
      <h1 class="h3 mb-3">My profile</h1>

      <div v-if="error" class="alert alert-danger">{{ error }}</div>
      <div v-if="success" class="alert alert-success">{{ success }}</div>

      <form @submit.prevent="submit" class="card card-body">
        <div class="mb-3">
          <label class="form-label">Email</label>
          <!-- Read-only: the email is the login identity, changing it is not
               part of the spec. -->
          <input class="form-control" :value="store.user ? store.user.email : ''" disabled />
        </div>

        <div class="mb-3">
          <label class="form-label" for="pname">Full name</label>
          <input id="pname" v-model.trim="form.full_name" class="form-control" required maxlength="120" />
        </div>

        <div class="mb-3">
          <label class="form-label" for="pphone">Phone</label>
          <input
            id="pphone"
            v-model.trim="form.phone"
            class="form-control"
            required
            pattern="[0-9]{10}"
            title="10 digits"
          />
        </div>

        <div class="mb-3">
          <label class="form-label" for="ppass">New password</label>
          <input id="ppass" v-model="password" type="password" class="form-control" minlength="8" />
          <div class="form-text">Leave blank to keep your current password.</div>
        </div>

        <div class="mb-3">
          <label class="form-label">Roles</label>
          <div>
            <span
              v-for="role in (store.user && store.user.roles) || []"
              :key="role"
              class="badge text-bg-secondary me-1"
            >
              {{ role }}
            </span>
          </div>
        </div>

        <button class="btn btn-success" :disabled="busy">
          {{ busy ? 'Saving...' : 'Save changes' }}
        </button>
      </form>
    </div>
  </div>
</template>
