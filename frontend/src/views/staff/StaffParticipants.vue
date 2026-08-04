<script>
/**
 * The registered trekkers for one trek.
 *
 * The trek id arrives in the URL (/staff/treks/:id/participants) and is read
 * from this.$route.params.id -- that is how the dashboard passes the selection
 * to this component.
 */
import { api } from '@/api'

export default {
  name: 'StaffParticipants',
  data() {
    return {
      participants: [],
      error: '',
      loading: true,
    }
  },
  computed: {
    trekId() {
      return this.$route.params.id
    },
  },
  async created() {
    try {
      this.participants = await api.participants(this.trekId)
    } catch (e) {
      this.error = e.message
    } finally {
      this.loading = false
    }
  },
  methods: {
    fmt(value) {
      if (!value) return '-'
      const d = new Date(value)
      return isNaN(d) ? value : d.toLocaleString()
    },
  },
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h3 mb-0">Participants &mdash; trek #{{ trekId }}</h1>
      <router-link class="btn btn-outline-secondary btn-sm" to="/staff">Back to my treks</router-link>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <p v-if="loading" class="text-muted">Loading...</p>
    <!-- Only say the trek is empty when the request actually succeeded;
         otherwise a refused request would claim nobody has booked. -->
    <p v-else-if="!error && participants.length === 0" class="text-muted">
      Nobody has booked this trek yet.
    </p>

    <div class="table-responsive" v-if="participants.length">
      <table class="table table-sm table-hover align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Booking</th>
            <th>Name</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Booked on</th>
            <th>Status</th>
            <th>Payment</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in participants" :key="row.booking_id || index">
            <td>{{ index + 1 }}</td>
            <td>#{{ row.booking_id }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.email }}</td>
            <td>{{ row.phone }}</td>
            <td>{{ fmt(row.booking_date) }}</td>
            <td>{{ row.booking_status }}</td>
            <td>{{ row.payment_status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
