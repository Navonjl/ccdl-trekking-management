<script>
/**
 * Admin dashboard: the counts the spec asks for (treks, users, staff, bookings)
 * plus an optional ChartJS bar chart of the most popular treks.
 *
 * Every tile is a link into the page that manages that thing, which is how the
 * admin moves from this component to AdminTreks/AdminUsers/etc.
 */
import { api } from '@/api'
import BarChart from '@/components/BarChart.vue'

export default {
  name: 'AdminDashboard',
  components: { BarChart },
  data() {
    return {
      stats: {},
      error: '',
      loading: true,
    }
  },
  async created() {
    try {
      this.stats = await api.stats()
    } catch (e) {
      this.error = e.message
    } finally {
      this.loading = false
    }
  },
  computed: {
    cards() {
      return [
        { label: 'Treks', value: this.num('total_treks', 'treks'), to: '/admin/treks' },
        { label: 'Trekkers', value: this.num('total_users', 'users'), to: '/admin/users' },
        { label: 'Staff', value: this.num('total_staff', 'staff'), to: '/admin/staff' },
        { label: 'Bookings', value: this.num('total_bookings', 'bookings'), to: '/admin/bookings' },
      ]
    },

    /**
     * Chart data for "popular treks". The chart is only rendered when the API
     * actually sends this list, so the dashboard still works without it.
     */
    popular() {
      const list = this.stats.popular_treks || this.stats.popular || []
      if (!Array.isArray(list)) return { labels: [], values: [] }
      return {
        labels: list.map((row) => row.name || row.trek_name || ''),
        values: list.map((row) => Number(row.bookings ?? row.booking_count ?? row.count ?? 0)),
      }
    },
  },
  methods: {
    /**
     * Read the first of these keys that holds a number. The backend is written
     * separately, so accept the obvious spellings rather than crashing on one.
     */
    num(...keys) {
      for (const key of keys) {
        const value = this.stats[key]
        if (typeof value === 'number') return value
      }
      return 0
    },
  },
}
</script>

<template>
  <div>
    <h1 class="h3 mb-3">Admin dashboard</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <p v-if="loading" class="text-muted">Loading statistics...</p>

    <div class="row row-cols-1 row-cols-sm-2 row-cols-lg-4 g-3 mb-4">
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
