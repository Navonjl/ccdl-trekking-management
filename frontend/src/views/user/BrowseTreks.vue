<script>
/**
 * Trekker dashboard: browse, search/filter and book treks.
 *
 * The filter boxes are sent to the server as query parameters
 * (/api/treks?q=...&difficulty=...) rather than filtering in the browser,
 * because the server is the one with the cached, indexed list.
 */
import { api } from '@/api'

export default {
  name: 'BrowseTreks',
  data() {
    return {
      treks: [],
      filters: { q: '', difficulty: '', location: '', min_days: '', max_days: '' },
      error: '',
      notice: '',
      loading: false,
      bookingId: null, // which trek's Book button is currently working
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.error = ''
      this.loading = true
      try {
        this.treks = await api.treks(this.filters)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    resetFilters() {
      this.filters = { q: '', difficulty: '', location: '', min_days: '', max_days: '' }
      this.load()
    },

    async book(trek) {
      this.error = ''
      this.notice = ''
      this.bookingId = trek.id
      try {
        await api.bookTrek(trek.id)
        this.notice = `Booked "${trek.name}". See it under My Bookings.`
        await this.load() // reload so the available slots shown are the new ones
      } catch (e) {
        // The server rejects overbooking / duplicate bookings / a closed trek;
        // whatever it says is shown here.
        this.error = e.message
      } finally {
        this.bookingId = null
      }
    },

    /** Bootstrap colour for the difficulty badge. */
    difficultyClass(difficulty) {
      if (difficulty === 'Hard') return 'text-bg-danger'
      if (difficulty === 'Moderate') return 'text-bg-warning'
      return 'text-bg-success'
    },

    canBook(trek) {
      return trek.status === 'Open' && trek.available_slots > 0
    },
  },
}
</script>

<template>
  <div>
    <h1 class="h3 mb-3">Available treks</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <!-- Search and filter -->
    <form class="card card-body mb-4" @submit.prevent="load">
      <div class="row g-2">
        <div class="col-md-4">
          <label class="form-label" for="q">Search</label>
          <input id="q" v-model.trim="filters.q" class="form-control" placeholder="name or location" />
        </div>
        <div class="col-md-2">
          <label class="form-label" for="difficulty">Difficulty</label>
          <select id="difficulty" v-model="filters.difficulty" class="form-select">
            <option value="">Any</option>
            <option>Easy</option>
            <option>Moderate</option>
            <option>Hard</option>
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label" for="location">Location</label>
          <input id="location" v-model.trim="filters.location" class="form-control" />
        </div>
        <div class="col-md-3">
          <label class="form-label">Duration (days)</label>
          <div class="input-group">
            <input v-model="filters.min_days" type="number" min="1" class="form-control" placeholder="min" />
            <input v-model="filters.max_days" type="number" min="1" class="form-control" placeholder="max" />
          </div>
        </div>
      </div>
      <div class="mt-3">
        <button class="btn btn-success" :disabled="loading">
          {{ loading ? 'Searching...' : 'Search' }}
        </button>
        <button type="button" class="btn btn-outline-secondary ms-2" @click="resetFilters">Reset</button>
      </div>
    </form>

    <p v-if="!loading && treks.length === 0" class="text-muted">
      No treks match your search.
    </p>

    <!-- One Bootstrap card per trek; row-cols-* makes it 1 column on a phone
         and 3 on a desktop, which covers the responsive requirement. -->
    <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">
      <div class="col" v-for="trek in treks" :key="trek.id">
        <div class="card h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <h5 class="card-title mb-1">{{ trek.name }}</h5>
              <span class="badge" :class="difficultyClass(trek.difficulty)">{{ trek.difficulty }}</span>
            </div>
            <h6 class="card-subtitle text-muted mb-2">{{ trek.location }}</h6>
            <p class="card-text small">{{ trek.description }}</p>

            <ul class="list-unstyled small mb-0">
              <li><strong>Duration:</strong> {{ trek.duration_days }} day(s)</li>
              <li><strong>Dates:</strong> {{ trek.start_date || '-' }} to {{ trek.end_date || '-' }}</li>
              <li><strong>Price:</strong> Rs. {{ trek.price }}</li>
              <li><strong>Slots left:</strong> {{ trek.available_slots }} / {{ trek.total_slots }}</li>
              <li><strong>Status:</strong> {{ trek.status }}</li>
              <li v-if="trek.assigned_staff_name"><strong>Guide:</strong> {{ trek.assigned_staff_name }}</li>
            </ul>
          </div>
          <div class="card-footer bg-white">
            <button
              class="btn btn-sm w-100"
              :class="canBook(trek) ? 'btn-success' : 'btn-secondary'"
              :disabled="!canBook(trek) || bookingId === trek.id"
              @click="book(trek)"
            >
              <span v-if="bookingId === trek.id">Booking...</span>
              <span v-else-if="trek.status !== 'Open'">Not open for booking</span>
              <span v-else-if="trek.available_slots <= 0">Fully booked</span>
              <span v-else>Book this trek</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
