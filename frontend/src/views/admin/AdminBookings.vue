<script>
/**
 * Every booking in the system: the admin's view of all historical trekking data.
 * Read-only on purpose -- cancelling belongs to the trekker, and trek status
 * belongs to the assigned staff.
 */
import { api } from '@/api'

export default {
  name: 'AdminBookings',
  data() {
    return {
      bookings: [],
      q: '',
      error: '',
      loading: false,
    }
  },
  created() {
    this.load()
  },
  computed: {
    // A one-line summary above the table, computed from the rows we already have
    // so it costs no extra request.
    counts() {
      const total = this.bookings.length
      const booked = this.bookings.filter((b) => b.status === 'Booked').length
      const completed = this.bookings.filter((b) => b.status === 'Completed').length
      const cancelled = this.bookings.filter((b) => b.status === 'Cancelled').length
      return { total, booked, completed, cancelled }
    },
  },
  methods: {
    async load() {
      this.error = ''
      this.loading = true
      try {
        this.bookings = await api.adminBookings(this.q)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    fmt(value) {
      if (!value) return '-'
      const d = new Date(value)
      return isNaN(d) ? value : d.toLocaleString()
    },

    statusClass(status) {
      if (status === 'Booked') return 'text-bg-primary'
      if (status === 'Completed') return 'text-bg-success'
      return 'text-bg-secondary'
    },
  },
}
</script>

<template>
  <div>
    <h1 class="h3 mb-3">All bookings</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <p class="text-muted">
      {{ counts.total }} total &middot; {{ counts.booked }} booked &middot;
      {{ counts.completed }} completed &middot; {{ counts.cancelled }} cancelled
    </p>

    <form class="row g-2 mb-3" @submit.prevent="load">
      <div class="col-sm-6 col-md-4">
        <input v-model.trim="q" class="form-control" placeholder="Search by trek or user" />
      </div>
      <div class="col-auto">
        <button class="btn btn-outline-success" :disabled="loading">Search</button>
      </div>
      <div class="col-auto">
        <button type="button" class="btn btn-outline-secondary" @click="q = ''; load()">Clear</button>
      </div>
    </form>

    <p v-if="!loading && bookings.length === 0" class="text-muted">No bookings found.</p>

    <div class="table-responsive" v-if="bookings.length">
      <table class="table table-sm table-hover align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Trekker</th>
            <th>Email</th>
            <th>Trek</th>
            <th>Location</th>
            <th>Booked on</th>
            <th>Status</th>
            <th>Payment</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id">
            <td>{{ b.id }}</td>
            <td>{{ b.user_name }}</td>
            <td>{{ b.user_email }}</td>
            <td>{{ b.trek_name }}</td>
            <td>{{ b.location }}</td>
            <td>{{ fmt(b.booking_date) }}</td>
            <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
            <td>{{ b.payment_status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
