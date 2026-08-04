<script>
/**
 * Staff dashboard: the treks the admin assigned to this staff member, with the
 * two things staff are allowed to change (available slots and status) editable
 * inline, plus the number of registered trekkers per trek.
 *
 * Each row keeps its own edited copy in `edits`, so typing in one row does not
 * disturb the others and nothing is sent until Save is pressed.
 */
import { api } from '@/api'

export default {
  name: 'StaffDashboard',
  data() {
    return {
      treks: [],
      edits: {}, // trek id -> { available_slots, status }
      error: '',
      notice: '',
      loading: false,
      savingId: null,
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
        this.treks = await api.staffDashboard()
        // Seed the editable copies from what the server sent.
        this.edits = {}
        for (const trek of this.treks) {
          this.edits[trek.id] = {
            available_slots: trek.available_slots,
            status: trek.status,
          }
        }
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    async save(trek) {
      const edit = this.edits[trek.id]
      this.error = ''
      this.notice = ''

      if (Number(edit.available_slots) > Number(trek.total_slots)) {
        this.error = `Available slots cannot exceed the ${trek.total_slots} total slots.`
        return
      }

      this.savingId = trek.id
      try {
        await api.updateStaffTrek(trek.id, {
          available_slots: Number(edit.available_slots),
          status: edit.status,
        })
        this.notice = `"${trek.name}" updated.`
        await this.load()
      } catch (e) {
        // The server refuses if this trek is not assigned to us.
        this.error = e.message
      } finally {
        this.savingId = null
      }
    },

    /** Registered trekkers for a trek, whatever the API decided to call it. */
    registered(trek) {
      return trek.registered_count ?? trek.participants_count ?? trek.bookings_count ?? '-'
    },
  },
}
</script>

<template>
  <div>
    <h1 class="h3 mb-3">My assigned treks</h1>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <p v-if="loading" class="text-muted">Loading...</p>
    <p v-else-if="treks.length === 0" class="text-muted">
      The admin has not assigned any treks to you yet.
    </p>

    <div class="row row-cols-1 row-cols-lg-2 g-3">
      <div class="col" v-for="trek in treks" :key="trek.id">
        <div class="card h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between">
              <h5 class="card-title mb-1">{{ trek.name }}</h5>
              <span class="badge text-bg-secondary">#{{ trek.id }}</span>
            </div>
            <h6 class="card-subtitle text-muted mb-3">
              {{ trek.location }} &middot; {{ trek.difficulty }} &middot;
              {{ trek.duration_days }} day(s)
            </h6>

            <ul class="list-unstyled small">
              <li><strong>Dates:</strong> {{ trek.start_date || '-' }} to {{ trek.end_date || '-' }}</li>
              <li><strong>Total slots:</strong> {{ trek.total_slots }}</li>
              <li><strong>Registered trekkers:</strong> {{ registered(trek) }}</li>
            </ul>

            <!-- Slots + status are the only fields staff may change. -->
            <form class="row g-2 align-items-end" @submit.prevent="save(trek)" v-if="edits[trek.id]">
              <div class="col-4">
                <label class="form-label small" :for="'slots' + trek.id">Available slots</label>
                <input
                  :id="'slots' + trek.id"
                  v-model="edits[trek.id].available_slots"
                  type="number"
                  min="0"
                  :max="trek.total_slots"
                  class="form-control form-control-sm"
                  required
                />
              </div>
              <div class="col-5">
                <label class="form-label small" :for="'status' + trek.id">Status</label>
                <select
                  :id="'status' + trek.id"
                  v-model="edits[trek.id].status"
                  class="form-select form-select-sm"
                  required
                >
                  <option>Open</option>
                  <option>Closed</option>
                  <option>Completed</option>
                </select>
              </div>
              <div class="col-3">
                <button class="btn btn-sm btn-success w-100" :disabled="savingId === trek.id">
                  {{ savingId === trek.id ? '...' : 'Save' }}
                </button>
              </div>
            </form>
          </div>

          <div class="card-footer bg-white">
            <!-- Navigating here mounts StaffParticipants.vue with this trek id. -->
            <router-link
              class="btn btn-sm btn-outline-success w-100"
              :to="'/staff/treks/' + trek.id + '/participants'"
            >
              View participants
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
