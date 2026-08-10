<script>
/**
 * The create/edit form for a trek, used by the admin Treks page.
 *
 * This is a child component, and it shows the standard Vue parent/child
 * contract: data comes DOWN through props (`trek`, `staff`) and events go UP
 * through emit ("save" with the edited values, "cancel" to close the form).
 * The child never talks to the API itself; AdminTreks.vue does that.
 *
 * Note: available_slots is NOT a field here. The server derives it
 * (total_slots minus the seats already booked), so letting the admin type a
 * number would only show a value the server is going to overwrite. Staff adjust
 * the free slots from their own dashboard.
 */
export default {
  name: 'TrekForm',
  props: {
    // null = creating a new trek, an object = editing that trek.
    trek: { type: Object, default: null },
    // List of staff, for the "assign staff" dropdown.
    staff: { type: Array, default: () => [] },
  },
  emits: ['save', 'cancel'],
  data() {
    return { form: this.blank() }
  },
  created() {
    this.fill()
  },
  watch: {
    // The parent keeps this component mounted and just swaps which trek is being
    // edited, so refill the fields when the prop changes.
    trek() {
      this.fill()
    },
  },
  computed: {
    editing() {
      return !!(this.trek && this.trek.id)
    },
  },
  methods: {
    blank() {
      return {
        name: '',
        location: '',
        description: '',
        difficulty: 'Easy',
        duration_days: 1,
        total_slots: 10,
        status: 'Pending',
        start_date: '',
        end_date: '',
        price: 0,
        assigned_staff_id: '',
      }
    },

    fill() {
      const t = this.trek
      if (!t) {
        this.form = this.blank()
        return
      }
      this.form = {
        name: t.name || '',
        location: t.location || '',
        description: t.description || '',
        difficulty: t.difficulty || 'Easy',
        duration_days: t.duration_days ?? 1,
        total_slots: t.total_slots ?? 0,
        status: t.status || 'Pending',
        start_date: t.start_date || '',
        end_date: t.end_date || '',
        price: t.price ?? 0,
        // '' rather than null so the <select> shows the "unassigned" option.
        assigned_staff_id: t.assigned_staff_id ?? '',
      }
    },

    submit() {
      const payload = { ...this.form }

      // Numbers: <input type="number"> gives strings, the API wants numbers.
      payload.duration_days = Number(payload.duration_days)
      payload.total_slots = Number(payload.total_slots)
      payload.price = Number(payload.price)

      // Empty dropdown/date means "no value", which the API expects as null.
      payload.assigned_staff_id =
        payload.assigned_staff_id === '' ? null : Number(payload.assigned_staff_id)
      if (!payload.start_date) payload.start_date = null
      if (!payload.end_date) payload.end_date = null

      // JS validation of a rule HTML5 attributes cannot express: date order.
      if (payload.start_date && payload.end_date && payload.end_date < payload.start_date) {
        alert('The end date cannot be before the start date.')
        return
      }

      this.$emit('save', payload)
    },
  },
}
</script>

<template>
  <form class="card card-body mb-4 border-success" @submit.prevent="submit">
    <h2 class="h5">{{ editing ? 'Edit trek #' + trek.id : 'New trek' }}</h2>

    <div class="row g-3">
      <div class="col-md-6">
        <label class="form-label" for="tname">Name</label>
        <input id="tname" v-model.trim="form.name" class="form-control" required maxlength="120" />
      </div>

      <div class="col-md-6">
        <label class="form-label" for="tloc">Location</label>
        <input id="tloc" v-model.trim="form.location" class="form-control" required maxlength="120" />
      </div>

      <div class="col-12">
        <label class="form-label" for="tdesc">Description</label>
        <textarea id="tdesc" v-model.trim="form.description" class="form-control" rows="2"></textarea>
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tdiff">Difficulty</label>
        <select id="tdiff" v-model="form.difficulty" class="form-select" required>
          <option>Easy</option>
          <option>Moderate</option>
          <option>Hard</option>
        </select>
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tdays">Duration (days)</label>
        <input id="tdays" v-model="form.duration_days" type="number" min="1" max="60" class="form-control" required />
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tslots">Total slots</label>
        <input id="tslots" v-model="form.total_slots" type="number" min="0" class="form-control" required />
      </div>

      <div class="col-md-3" v-if="editing">
        <label class="form-label">Slots free now</label>
        <!-- Read-only: the server keeps this in step with the bookings. -->
        <input class="form-control" :value="trek.available_slots + ' of ' + trek.total_slots" disabled />
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tprice">Price (Rs.)</label>
        <input id="tprice" v-model="form.price" type="number" min="0" step="0.01" class="form-control" required />
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tstatus">Status</label>
        <select id="tstatus" v-model="form.status" class="form-select" required>
          <option>Pending</option>
          <option>Approved</option>
          <option>Open</option>
          <option>Closed</option>
          <option>Completed</option>
        </select>
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tstart">Start date</label>
        <input id="tstart" v-model="form.start_date" type="date" class="form-control" />
      </div>

      <div class="col-md-3">
        <label class="form-label" for="tend">End date</label>
        <input id="tend" v-model="form.end_date" type="date" class="form-control" />
      </div>

      <div class="col-md-6">
        <label class="form-label" for="tstaff">Assigned staff</label>
        <select id="tstaff" v-model="form.assigned_staff_id" class="form-select">
          <option value="">-- none --</option>
          <option v-for="s in staff" :key="s.id" :value="s.id">
            {{ s.name }} ({{ s.employee_code }})
          </option>
        </select>
      </div>
    </div>

    <div class="mt-3">
      <button class="btn btn-success">{{ editing ? 'Save changes' : 'Create trek' }}</button>
      <button type="button" class="btn btn-outline-secondary ms-2" @click="$emit('cancel')">Cancel</button>
    </div>
  </form>
</template>
