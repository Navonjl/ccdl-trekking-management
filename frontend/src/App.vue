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
  <!-- Decorative background: drifting clouds over a mountain ridge. -->
  <div class="sky" aria-hidden="true">
    <svg v-for="n in 3" :key="n" :class="['sky-cloud', 'sky-cloud-' + n]" viewBox="0 0 120 50">
      <g fill="#fff">
        <circle cx="35" cy="30" r="16" />
        <circle cx="62" cy="22" r="20" />
        <circle cx="88" cy="32" r="14" />
        <rect x="18" y="30" width="86" height="18" rx="9" />
      </g>
    </svg>
    <svg class="sky-ridge" viewBox="0 0 1440 200" preserveAspectRatio="none">
      <path
        d="M0 200 L0 120 L120 70 L220 110 L360 40 L480 100 L600 60 L760 130 L900 50 L1040 110 L1160 70 L1300 120 L1440 80 L1440 200 Z"
        fill="#d6e6fb"
      />
      <path
        d="M0 200 L0 160 L160 110 L300 150 L440 100 L620 160 L780 120 L940 165 L1100 115 L1260 150 L1440 125 L1440 200 Z"
        fill="#c0d8f6"
      />
    </svg>
  </div>

  <NavBar v-if="store.token" />

  <main class="container py-4">
    <router-view />
  </main>

  <footer class="app-footer container text-center py-3">
    <small>Head in the Clouds &middot; MIT CCDL project</small>
  </footer>
</template>
