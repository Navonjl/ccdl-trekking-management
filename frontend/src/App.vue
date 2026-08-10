<script>
/**
 * The root component. It is the only component that is always on screen.
 *
 * Structure of the whole app:
 *   App.vue
 *     +-- NavBar.vue          (always visible once logged in)
 *     +-- <router-view />     (swapped by vue-router for the current URL)
 *
 * So "control shifts" like this: a click on a router-link changes the URL, the
 * router guard in router/index.js checks the token/role, and the router replaces
 * whatever is inside <router-view> with the new view component.
 */
import NavBar from '@/components/NavBar.vue'
import { store } from '@/store'

export default {
  name: 'App',
  components: { NavBar },
  data() {
    return { store }
  },
  watch: {
    // api.js clears the token when the server rejects it (HTTP 401). Watching
    // it here is what turns "token gone" into "back to the login page", without
    // api.js needing to know that the router exists.
    'store.token'(value) {
      if (!value && this.$route.name !== 'login' && this.$route.name !== 'register') {
        this.$router.push({ name: 'login' })
      }
    },
  },
}
</script>

<template>
  <NavBar v-if="store.token" />

  <main class="container py-4">
    <router-view />
  </main>

  <footer class="container text-center text-muted py-3 border-top">
    <small>Trekking Management Application (IITM MAD-2 project)</small>
  </footer>
</template>
