<script>
/**
 * Staff management: list, search, add a new staff member, deactivate/reactivate.
 *
 * Staff cannot register themselves, so this page is the only way a staff login
 * comes into existence.
 */
import { api } from '@/api'

export default {
  name: 'AdminStaff',
  data() {
    return {
      staff: [],
      q: '',
      showForm: false,
      form: { full_name: '', email: '', phone: '', password: '', employee_code: '' },
      error: '',
      notice: '',
      loading: false,
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
        this.staff = await api.adminStaff(this.q)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    async create() {
      this.error = ''
      this.notice = ''
      try {
        await api.createStaff(this.form)
        this.notice = `Staff ${this.form.email} created.`
        this.form = { full_name: '', email: '', phone: '', password: '', employee_code: '' }
        this.showForm = false
        await this.load()
      } catch (e) {
        this.error = e.message
      }
    },

    /**
     * Deactivating flips User.active, which is what Flask-Security checks at
     * login, so a deactivated staff member simply cannot log in any more.
     *
     * Note it calls the /admin/users/... endpoint with member.user_id, not the
     * staff profile id: staff and trekkers live in ONE user table, so there is
     * one pair of deactivate/reactivate routes for both.
     */
    async toggleActive(member) {
      const turningOff = member.active !== false
      const action = turningOff ? 'deactivate' : 'reactivate'
      if (!confirm(`${action} ${member.name || member.email}?`)) return

      this.error = ''
      this.notice = ''
      try {
        await api.userAction(member.user_id, action)
        this.notice = `${member.name || member.email}: ${action} done.`
        await this.load()
      } catch (e) {
        this.error = e.message
      }
    },
  },
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h3 mb-0">Trek staff</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Close' : '+ Add staff' }}
      </button>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="notice" class="alert alert-success">{{ notice }}</div>

    <form v-if="showForm" class="card card-body mb-4 border-success" @submit.prevent="create">
      <h2 class="h5">New staff member</h2>
      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label" for="sname">Full name</label>
          <input id="sname" v-model.trim="form.full_name" class="form-control" required maxlength="120" />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="semail">Email</label>
          <input id="semail" v-model.trim="form.email" type="email" class="form-control" required />
        </div>
        <div class="col-md-4">
          <label class="form-label" for="sphone">Phone</label>
          <input id="sphone" v-model.trim="form.phone" class="form-control" required pattern="[0-9]{10}" title="10 digits" />
        </div>
        <div class="col-md-4">
          <label class="form-label" for="scode">Employee code</label>
          <input id="scode" v-model.trim="form.employee_code" class="form-control" maxlength="32" />
          <!-- Optional: the server generates STF001, STF002, ... when left blank. -->
          <div class="form-text">Leave blank to auto-generate.</div>
        </div>
        <div class="col-md-4">
          <label class="form-label" for="spass">Temporary password</label>
          <input id="spass" v-model="form.password" type="password" class="form-control" required minlength="6" />
          <div class="form-text">At least 6 characters.</div>
        </div>
      </div>
      <div class="mt-3">
        <button class="btn btn-primary">Create staff</button>
      </div>
    </form>

    <form class="row g-2 mb-3" @submit.prevent="load">
      <div class="col-sm-6 col-md-4">
        <input v-model.trim="q" class="form-control" placeholder="Search staff by name, email or code" />
      </div>
      <div class="col-auto">
        <button class="btn btn-outline-primary" :disabled="loading">Search</button>
      </div>
      <div class="col-auto">
        <button type="button" class="btn btn-outline-secondary" @click="q = ''; load()">Clear</button>
      </div>
    </form>

    <p v-if="!loading && staff.length === 0" class="text-muted">No staff found.</p>

    <div class="table-responsive" v-if="staff.length">
      <table class="table table-sm table-hover align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Code</th>
            <th>Treks</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="member in staff" :key="member.id">
            <td>{{ member.id }}</td>
            <td>{{ member.name }}</td>
            <td>{{ member.email }}</td>
            <td>{{ member.phone }}</td>
            <td>{{ member.employee_code }}</td>
            <td>{{ member.assigned_trek_count }}</td>
            <td>
              <span class="badge" :class="member.active === false ? 'text-bg-secondary' : 'text-bg-success'">
                {{ member.active === false ? 'Inactive' : 'Active' }}
              </span>
            </td>
            <td class="text-end">
              <button
                class="btn btn-sm"
                :class="member.active === false ? 'btn-outline-primary' : 'btn-outline-danger'"
                @click="toggleActive(member)"
              >
                {{ member.active === false ? 'Reactivate' : 'Deactivate' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
