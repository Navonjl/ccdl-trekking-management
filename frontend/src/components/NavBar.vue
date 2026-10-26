<script>
/**
 * Top navigation. Which links appear depends on the role of the logged-in user,
 * so a trekker is never shown a link into the admin pages.
 */
import { api } from '@/api'
import BrandLogo from '@/components/BrandLogo.vue'
import { store } from '@/store'

export default {
  name: 'NavBar',
  components: { BrandLogo },
  data() {
    return { store }
  },
  methods: {
    async logout() {
      // Tell the server too, so it can invalidate the session. If that call
      // fails we still log out locally, since the user asked to leave.
      try {
        await api.logout()
      } catch {
        // ignored on purpose
      }
      store.logout()
      this.$router.push({ name: 'login' })
    },
  },
}
</script>

<template>
  <nav class="navbar navbar-expand-lg navbar-cloud sticky-top">
    <div class="container">
      <router-link class="navbar-brand" :to="store.homePath()">
        <BrandLogo class="brand-logo" />
        Head in the Clouds
      </router-link>

      <!-- data-bs-* attributes are handled by the Bootstrap JS bundle imported
           in main.js; this is the hamburger menu on small screens. -->
      <button
        class="navbar-toggler"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#navLinks"
      >
        <span class="navbar-toggler-icon"></span>
      </button>

      <div class="collapse navbar-collapse" id="navLinks">
        <ul class="navbar-nav me-auto">
          <template v-if="store.hasRole('admin')">
            <li class="nav-item"><router-link class="nav-link" to="/admin">Dashboard</router-link></li>
            <li class="nav-item"><router-link class="nav-link" to="/admin/treks">Treks</router-link></li>
            <li class="nav-item"><router-link class="nav-link" to="/admin/staff">Staff</router-link></li>
            <li class="nav-item"><router-link class="nav-link" to="/admin/users">Users</router-link></li>
            <li class="nav-item"><router-link class="nav-link" to="/admin/bookings">Bookings</router-link></li>
          </template>

          <template v-else-if="store.hasRole('staff')">
            <li class="nav-item"><router-link class="nav-link" to="/staff">My Treks</router-link></li>
          </template>

          <template v-else>
            <li class="nav-item"><router-link class="nav-link" to="/treks">Browse Treks</router-link></li>
            <li class="nav-item"><router-link class="nav-link" to="/bookings">My Bookings</router-link></li>
          </template>
        </ul>

        <ul class="navbar-nav">
          <li class="nav-item">
            <router-link class="nav-link" to="/profile">
              {{ store.user ? store.user.email : 'Profile' }}
            </router-link>
          </li>
          <li class="nav-item">
            <button class="btn btn-sm btn-outline-primary mt-1 ms-lg-2" @click="logout">Logout</button>
          </li>
        </ul>
      </div>
    </div>
  </nav>
</template>
