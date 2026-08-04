<script>
/**
 * "My bookings" = current bookings + trekking history + the CSV export.
 *
 * The export is the user-triggered async job. The server hands it to Celery and
 * answers immediately with a task id, so this view then POLLS
 * /api/exports/<task_id> every 1.5s until the job reports SUCCESS. That is why
 * there is a timer here at all.
 */
import { api } from '@/api'

export default {
  name: 'MyBookings',
  data() {
    return {
      bookings: [],
      error: '',
      notice: '',
      loading: false,

      // CSV export job state
      taskId: '',
      exportState: '', // '' | PENDING | STARTED | SUCCESS | FAILURE
      exportFile: '',
      exportError: '',
      timer: null,
      stopped: false,
    }
  },
  computed: {
    // Still-active reservations the user can cancel.
    active() {
      return this.bookings.filter((b) => b.status === 'Booked')
    },
    // Everything finished: the trekking history the spec asks for.
    history() {
      return this.bookings.filter((b) => b.status !== 'Booked')
    },
  },
  created() {
    this.load()
  },
  // Without this, the poll would keep firing after the user navigates away.
  beforeUnmount() {
    this.stopped = true
    if (this.timer) clearTimeout(this.timer)
  },
  methods: {
    async load() {
      this.error = ''
      this.loading = true
      try {
        this.bookings = await api.bookings()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    async cancel(booking) {
      if (!confirm(`Cancel your booking for "${booking.trek_name}"?`)) return
      this.error = ''
      this.notice = ''
      try {
        await api.cancelBooking(booking.id)
        this.notice = 'Booking cancelled.'
        await this.load()
      } catch (e) {
        this.error = e.message
      }
    },

    /* ---- CSV export ---- */

    async startExport() {
      this.exportError = ''
      this.exportFile = ''
      this.exportState = 'PENDING'
      try {
        const data = await api.startExport()
        // Accept the usual spellings of the id field.
        this.taskId = data.task_id || data.taskId || data.id || ''
        if (!this.taskId) throw new Error('The server did not return a task id.')
        this.poll()
      } catch (e) {
        this.exportState = ''
        this.exportError = e.message
      }
    },

    async poll() {
      if (this.stopped || !this.taskId) return
      try {
        const data = await api.exportStatus(this.taskId)

        const state = String(data.state || data.status || '').toUpperCase()
        // The filename may come back at the top level or inside a result object.
        const raw = data.filename || (data.result && (data.result.filename || data.result)) || ''
        // Keep only the file name even if the server returned a full path.
        const filename = typeof raw === 'string' ? raw.split('/').pop() : ''

        if (state === 'FAILURE') {
          this.exportState = 'FAILURE'
          this.exportError = data.error || 'The export job failed.'
          return
        }
        if (filename || state === 'SUCCESS') {
          this.exportState = 'SUCCESS'
          this.exportFile = filename
          return
        }

        this.exportState = state || 'PENDING'
        this.timer = setTimeout(this.poll, 1500) // ask again shortly
      } catch (e) {
        this.exportState = ''
        this.exportError = e.message
      }
    },

    async download() {
      this.exportError = ''
      try {
        await api.downloadExport(this.exportFile)
      } catch (e) {
        this.exportError = e.message
      }
    },

    /** ISO timestamp from the API -> something readable. */
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
    <h1 class="h3 mb-3">My bookings</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <!-- Async job: export the trekking history as CSV -->
    <div class="card card-body mb-4">
      <h2 class="h6">Export my trekking history</h2>
      <p class="small text-muted mb-2">
        Runs as a background job on the server; the download appears here when it
        finishes.
      </p>

      <div class="d-flex align-items-center gap-2 flex-wrap">
        <button
          class="btn btn-outline-success btn-sm"
          @click="startExport"
          :disabled="exportState === 'PENDING' || exportState === 'STARTED'"
        >
          Export as CSV
        </button>

        <span v-if="exportState === 'PENDING' || exportState === 'STARTED'" class="small text-muted">
          Working... (task {{ taskId }})
        </span>

        <button v-if="exportState === 'SUCCESS'" class="btn btn-success btn-sm" @click="download">
          Download {{ exportFile }}
        </button>
      </div>

      <div v-if="exportState === 'SUCCESS'" class="alert alert-success py-2 mt-2 mb-0 small">
        Your export is ready.
      </div>
      <div v-if="exportError" class="alert alert-danger py-2 mt-2 mb-0 small">{{ exportError }}</div>
    </div>

    <!-- Current bookings -->
    <h2 class="h5">Current bookings</h2>
    <p v-if="!loading && active.length === 0" class="text-muted">
      You have no active bookings. <router-link to="/treks">Browse treks</router-link>.
    </p>

    <div v-if="active.length" class="table-responsive mb-4">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Trek</th>
            <th>Location</th>
            <th>Booked on</th>
            <th>Status</th>
            <th>Payment</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in active" :key="b.id">
            <td>{{ b.id }}</td>
            <td>{{ b.trek_name }}</td>
            <td>{{ b.location }}</td>
            <td>{{ fmt(b.booking_date) }}</td>
            <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
            <td>{{ b.payment_status }}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-danger" @click="cancel(b)">Cancel</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- History -->
    <h2 class="h5">Trekking history</h2>
    <p v-if="!loading && history.length === 0" class="text-muted">Nothing here yet.</p>

    <div v-if="history.length" class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Trek</th>
            <th>Location</th>
            <th>Booked on</th>
            <th>Status</th>
            <th>Payment</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in history" :key="b.id">
            <td>{{ b.id }}</td>
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
