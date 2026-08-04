<script>
/**
 * Admin dashboard: the counts the spec asks for, plus a ChartJS bar chart of the
 * most popular treks.
 *
 * Two requests are made. /api/admin/stats gives the counts (it is cached in
 * Redis on the server, so it is cheap). The chart needs bookings-per-trek, which
 * stats does not provide, so the booking list is fetched and grouped here -- the
 * admin bookings page needs that same list anyway.
 *
 * Every count tile is a link into the page that manages that thing, which is how
 * the admin moves from this component to AdminTreks/AdminUsers/etc.
 */
import { api } from '@/api'
import BarChart from '@/components/BarChart.vue'

export default {
  name: 'AdminDashboard',
  components: { BarChart },
  data() {
    return {
      stats: {},
      bookings: [],
      error: '',
      loading: true,
    }
  },
  async created() {
    try {
      this.stats = await api.stats()
    } catch (e) {
      this.error = e.message
    }
    try {
      this.bookings = await api.adminBookings()
    } catch {
      // The chart is a nice-to-have; the counts above still work without it.
      this.bookings = []
    }
    this.loading = false
  },
  computed: {
    cards() {
      return [
        { label: 'Treks', value: this.num('total_treks'), to: '/admin/treks' },
        { label: 'Trekkers', value: this.num('total_users'), to: '/admin/users' },
        { label: 'Staff', value: this.num('total_staff'), to: '/admin/staff' },
        { label: 'Bookings', value: this.num('total_bookings'), to: '/admin/bookings' },
      ]
    },

    /**
     * Bookings grouped by trek name, biggest first, top 5. Cancelled bookings do
     * not count towards "popular".
     */
    popular() {
      const totals = {}
      for (const b of this.bookings) {
        if (b.status === 'Cancelled') continue
        const name = b.trek_name || '(unknown)'
        totals[name] = (totals[name] || 0) + 1
      }
      const top = Object.entries(totals)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
      return { labels: top.map((row) => row[0]), values: top.map((row) => row[1]) }
    },
  },
  methods: {
    /** Read a count out of the stats object, 0 if the key is missing. */
    num(key) {
      return typeof this.stats[key] === 'number' ? this.stats[key] : 0
    },
  },
}
</script>

<template>
  <div>
    <h1 class="h3 mb-3">Admin dashboard</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <p v-if="loading" class="text-muted">Loading statistics...</p>

    <div class="row row-cols-1 row-cols-sm-2 row-cols-lg-4 g-3 mb-3">
      <div class="col" v-for="card in cards" :key="card.label">
        <router-link class="text-decoration-none" :to="card.to">
          <div class="card text-center h-100">
            <div class="card-body">
              <div class="display-6">{{ card.value }}</div>
              <div class="text-muted">{{ card.label }}</div>
            </div>
          </div>
        </router-link>
      </div>
    </div>

    <p class="text-muted">
      {{ num('open_treks') }} trek(s) open for booking &middot;
      {{ num('completed_treks') }} completed
    </p>

    <div class="card card-body mb-4" v-if="popular.labels.length">
      <h2 class="h5">Most popular treks</h2>
      <BarChart :labels="popular.labels" :values="popular.values" label="Bookings" />
    </div>

    <div class="card card-body">
      <h2 class="h5">Manage</h2>
      <div class="d-flex flex-wrap gap-2">
        <router-link class="btn btn-outline-success" to="/admin/treks">Treks &amp; assignments</router-link>
        <router-link class="btn btn-outline-success" to="/admin/staff">Trek staff</router-link>
        <router-link class="btn btn-outline-success" to="/admin/users">Users</router-link>
        <router-link class="btn btn-outline-success" to="/admin/bookings">All bookings</router-link>
      </div>
    </div>
  </div>
</template>
