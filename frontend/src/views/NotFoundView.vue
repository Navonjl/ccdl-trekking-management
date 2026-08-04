<script>
import { store } from '@/store'

export default {
  name: 'NotFoundView',
  data() {
    return { store }
  },
}
</script>

<template>
  <div class="text-center py-5">
    <h1 class="display-6">Page not found</h1>
    <p class="text-muted">There is nothing at this address.</p>
    <router-link class="btn btn-success" :to="store.token ? store.homePath() : '/login'">
      Go back
    </router-link>
  </div>
</template>
