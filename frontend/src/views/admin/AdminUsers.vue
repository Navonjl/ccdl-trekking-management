<script>
/**
 * User management: list, search, deactivate and blacklist.
 *
 * Deactivate and blacklist are two different things, which is why there are two
 * buttons: `active` is Flask-Security's own flag and stops the login, while
 * `is_blacklisted` is our column and is checked by blocked_check() in the API so
 * a blacklisted user who is still logged in cannot do anything either.
 */
import { api } from '@/api'

export default {
  name: 'AdminUsers',
  data() {
    return {
      users: [],
      q: '',
      error: '',
      notice: '',
      loading: false,
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.error = ''
      this.loading = true
      try {
        this.users = await api.adminUsers(this.q)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    /**
     * One method for all four buttons. The server exposes each state change as
     * its own action (POST .../deactivate, .../blacklist, ...), so `action` is
     * simply the last part of the URL.
     */
    async act(user, action) {
      if (!confirm(`${action} ${user.email}?`)) return
      this.error = ''
      this.notice = ''
      try {
        await api.userAction(user.id, action)
        this.notice = `${user.email}: ${action} done.`
        await this.load()
      } catch (e) {
        // The server refuses to touch the admin account itself.
        this.error = e.message
      }
    },
  },
}
</script>

<template>
  <div>
    <h1 class="h3 mb-3">Users</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <form class="row g-2 mb-3" @submit.prevent="load">
      <div class="col-sm-6 col-md-4">
        <input v-model.trim="q" class="form-control" placeholder="Search users by name or email" />
      </div>
      <div class="col-auto">
        <button class="btn btn-outline-primary" :disabled="loading">Search</button>
      </div>
      <div class="col-auto">
        <button type="button" class="btn btn-outline-secondary" @click="q = ''; load()">Clear</button>
      </div>
    </form>

    <p v-if="!loading && users.length === 0" class="text-muted">No users found.</p>

    <div class="table-responsive" v-if="users.length">
      <table class="table table-sm table-hover align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Bookings</th>
            <th>Roles</th>
            <th>State</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.full_name }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.phone }}</td>
            <td>{{ user.booking_count ?? '-' }}</td>
            <td>
              <span v-for="role in user.roles || []" :key="role" class="badge text-bg-secondary me-1">
                {{ role }}
              </span>
            </td>
            <td>
              <span class="badge me-1" :class="user.active === false ? 'text-bg-secondary' : 'text-bg-success'">
                {{ user.active === false ? 'Inactive' : 'Active' }}
              </span>
              <span v-if="user.is_blacklisted" class="badge text-bg-danger">Blacklisted</span>
            </td>
            <td class="text-end text-nowrap">
              <button
                v-if="user.active === false"
                class="btn btn-sm btn-outline-success me-1"
                @click="act(user, 'reactivate')"
              >
                Reactivate
              </button>
              <button
                v-else
                class="btn btn-sm btn-outline-warning me-1"
                @click="act(user, 'deactivate')"
              >
                Deactivate
              </button>

              <button
                v-if="user.is_blacklisted"
                class="btn btn-sm btn-outline-secondary"
                @click="act(user, 'unblacklist')"
              >
                Un-blacklist
              </button>
              <button v-else class="btn btn-sm btn-outline-danger" @click="act(user, 'blacklist')">
                Blacklist
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
