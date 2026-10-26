<script>
/**
 * Trek CRUD for the admin, including assigning a staff member to a trek
 * (assigned_staff_id is just another field on the trek).
 *
 * This component owns the data and the API calls; the TrekForm child owns the
 * input fields. Clicking "Edit" sets `editing`, which is passed down as a prop;
 * the child emits "save" and this component sends it to the server.
 */
import { api } from '@/api'
import TrekForm from '@/components/TrekForm.vue'

export default {
  name: 'AdminTreks',
  components: { TrekForm },
  data() {
    return {
      treks: [],
      staff: [],
      q: '',
      showForm: false,
      editing: null, // null while creating, the trek object while editing
      error: '',
      notice: '',
      loading: false,
    }
  },
  async created() {
    await this.load()
    // The staff list is only needed to fill the "assign staff" dropdown.
    try {
      this.staff = await api.adminStaff()
    } catch {
      this.staff = []
    }
  },
  methods: {
    async load() {
      this.error = ''
      this.loading = true
      try {
        this.treks = await api.adminTreks(this.q)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    newTrek() {
      this.editing = null
      this.showForm = true
    },

    edit(trek) {
      this.editing = trek
      this.showForm = true
      window.scrollTo({ top: 0 })
    },

    closeForm() {
      this.showForm = false
      this.editing = null
    },

    /**
     * Handler for the child's "save" event: one method for create and update.
     *
     * Two requests, not one: the trek fields go to /admin/treks, but the staff
     * assignment has its own endpoint (the server validates there that the staff
     * member exists and is active). We only call it when the choice changed.
     */
    async save(payload) {
      this.error = ''
      this.notice = ''

      // assigned_staff_id is not a column the trek endpoints accept, so take it
      // out of the body before sending the rest.
      const { assigned_staff_id: staffId, ...trekFields } = payload

      try {
        let trekId
        if (this.editing) {
          const updated = await api.updateTrek(this.editing.id, trekFields)
          trekId = updated.id ?? this.editing.id
          if (staffId !== (this.editing.assigned_staff_id ?? null)) {
            await api.assignStaff(trekId, staffId)
          }
          this.notice = 'Trek updated.'
        } else {
          const created = await api.createTrek(trekFields)
          trekId = created.id
          if (staffId !== null && trekId) {
            await api.assignStaff(trekId, staffId)
          }
          this.notice = 'Trek created.'
        }
        this.closeForm()
        await this.load()
      } catch (e) {
        this.error = e.message
      }
    },

    async remove(trek) {
      if (!confirm(`Remove "${trek.name}"? This cannot be undone.`)) return
      this.error = ''
      this.notice = ''
      try {
        await api.deleteTrek(trek.id)
        this.notice = 'Trek removed.'
        await this.load()
      } catch (e) {
        this.error = e.message
      }
    },

    statusClass(status) {
      if (status === 'Open') return 'text-bg-success'
      if (status === 'Completed') return 'text-bg-primary'
      if (status === 'Closed') return 'text-bg-dark'
      if (status === 'Approved') return 'text-bg-info'
      return 'text-bg-secondary'
    },
  },
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h3 mb-0">Treks</h1>
      <button class="btn btn-primary" @click="newTrek">+ New trek</button>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <!-- Child component. :trek and :staff go down, @save/@cancel come back up. -->
    <TrekForm
      v-if="showForm"
      :trek="editing"
      :staff="staff"
      @save="save"
      @cancel="closeForm"
    />

    <form class="row g-2 mb-3" @submit.prevent="load">
      <div class="col-sm-6 col-md-4">
        <input v-model.trim="q" class="form-control" placeholder="Search treks by name or location" />
      </div>
      <div class="col-auto">
        <button class="btn btn-outline-primary" :disabled="loading">Search</button>
      </div>
      <div class="col-auto">
        <button type="button" class="btn btn-outline-secondary" @click="q = ''; load()">Clear</button>
      </div>
    </form>

    <p v-if="!loading && treks.length === 0" class="text-muted">No treks yet.</p>

    <div class="table-responsive" v-if="treks.length">
      <table class="table table-sm table-hover align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Location</th>
            <th>Difficulty</th>
            <th>Days</th>
            <th>Slots</th>
            <th>Dates</th>
            <th>Price</th>
            <th>Staff</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="trek in treks" :key="trek.id">
            <td>{{ trek.id }}</td>
            <td>{{ trek.name }}</td>
            <td>{{ trek.location }}</td>
            <td>{{ trek.difficulty }}</td>
            <td>{{ trek.duration_days }}</td>
            <td>{{ trek.available_slots }}/{{ trek.total_slots }}</td>
            <td class="small">{{ trek.start_date || '-' }}<br />{{ trek.end_date || '-' }}</td>
            <td>{{ trek.price }}</td>
            <td>{{ trek.assigned_staff_name || '-' }}</td>
            <td><span class="badge" :class="statusClass(trek.status)">{{ trek.status }}</span></td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-outline-primary me-1" @click="edit(trek)">Edit</button>
              <button class="btn btn-sm btn-outline-danger" @click="remove(trek)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
