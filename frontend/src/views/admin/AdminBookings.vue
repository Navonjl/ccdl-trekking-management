<script>
/**
 * Every booking in the system: the admin's view of all historical trekking data.
 * Read-only on purpose: cancelling belongs to the trekker, and trek status
 * belongs to the assigned staff.
 */
import { api } from '@/api'

export default {
  name: 'AdminBookings',
  data() {
    return {
      bookings: [],
      // These two are what the API filters on (?status= and ?trek_id=).
      filters: { status: '', trek_id: '' },
      // The free-text box is applied here in the browser, because the admin
      // bookings endpoint has no ?q= parameter.
      q: '',
      error: '',
      notice: '',
      loading: false,
    }
  },
  created() {
    this.load()
  },
  computed: {
    /** The rows actually shown: server results narrowed by the text box. */
    visible() {
      const q = this.q.toLowerCase()
      if (!q) return this.bookings
      return this.bookings.filter(
        (b) =>
          (b.trek_name || '').toLowerCase().includes(q) ||
          (b.user_name || '').toLowerCase().includes(q) ||
          (b.user_email || '').toLowerCase().includes(q),
      )
    },

    // A one-line summary above the table, computed from the rows we already have
    // so it costs no extra request.
    counts() {
      const rows = this.visible
      return {
        total: rows.length,
        booked: rows.filter((b) => b.status === 'Booked').length,
        completed: rows.filter((b) => b.status === 'Completed').length,
        cancelled: rows.filter((b) => b.status === 'Cancelled').length,
      }
    },
  },
  methods: {
    async load() {
      this.error = ''
      this.loading = true
      try {
        this.bookings = await api.adminBookings(this.filters)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    async markPaid(booking) {
      this.error = ''
      this.notice = ''
      try {
        const updated = await api.markBookingPaid(booking.id)
        booking.payment_status = updated.payment_status
        this.notice = `Booking #${booking.id} marked as paid.`
      } catch (e) {
        this.error = e.message
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
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <p class="text-muted">
      {{ counts.total }} total &middot; {{ counts.booked }} booked &middot;
      {{ counts.completed }} completed &middot; {{ counts.cancelled }} cancelled
    </p>

    <form class="row g-2 mb-3 align-items-end" @submit.prevent="load">
      <div class="col-sm-5 col-md-4">
        <label class="form-label" for="bq">Search (in the loaded rows)</label>
        <input id="bq" v-model.trim="q" class="form-control" placeholder="trek, user or email" />
      </div>
      <div class="col-sm-3 col-md-2">
        <label class="form-label" for="bstatus">Status</label>
        <select id="bstatus" v-model="filters.status" class="form-select" @change="load">
          <option value="">Any</option>
          <option>Booked</option>
          <option>Cancelled</option>
          <option>Completed</option>
        </select>
      </div>
      <div class="col-sm-2">
        <label class="form-label" for="btrek">Trek id</label>
        <input id="btrek" v-model="filters.trek_id" type="number" min="1" class="form-control" />
      </div>
      <div class="col-auto">
        <button class="btn btn-outline-success" :disabled="loading">Apply</button>
      </div>
      <div class="col-auto">
        <button
          type="button"
          class="btn btn-outline-secondary"
          @click="q = ''; filters = { status: '', trek_id: '' }; load()"
        >
          Clear
        </button>
      </div>
    </form>

    <p v-if="!loading && visible.length === 0" class="text-muted">No bookings found.</p>

    <div class="table-responsive" v-if="visible.length">
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
            <!-- Holds the "Mark as paid" button, so it has no title. -->
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in visible" :key="b.id">
            <td>{{ b.id }}</td>
            <td>{{ b.user_name }}</td>
            <td>{{ b.user_email }}</td>
            <td>{{ b.trek_name }}</td>
            <td>{{ b.location }}</td>
            <td>{{ fmt(b.booking_date) }}</td>
            <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
            <td>{{ b.payment_status }}</td>
            <td>
              <!-- There is no real payment gateway; the admin just records
                   that the money came in. -->
              <button
                v-if="b.payment_status !== 'Paid' && b.status !== 'Cancelled'"
                class="btn btn-sm btn-outline-success"
                @click="markPaid(b)"
              >
                Mark as paid
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
