/**
 * The route table: which URL shows which view component.
 *
 * Two custom fields are attached to routes with `meta`, and the single guard at
 * the bottom of this file is what reads them:
 *   meta.requiresAuth  must be logged in
 *   meta.role          must additionally hold that role
 */
import { createRouter, createWebHistory } from 'vue-router'
import { store } from '@/store'

import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import ProfileView from '@/views/ProfileView.vue'

import AdminDashboard from '@/views/admin/AdminDashboard.vue'
import AdminTreks from '@/views/admin/AdminTreks.vue'
import AdminStaff from '@/views/admin/AdminStaff.vue'
import AdminUsers from '@/views/admin/AdminUsers.vue'
import AdminBookings from '@/views/admin/AdminBookings.vue'

import StaffDashboard from '@/views/staff/StaffDashboard.vue'
import StaffParticipants from '@/views/staff/StaffParticipants.vue'

import BrowseTreks from '@/views/user/BrowseTreks.vue'
import MyBookings from '@/views/user/MyBookings.vue'

const routes = [
  // "/" is not a page of its own: it bounces you to the dashboard for your role.
  { path: '/', redirect: () => (store.token ? store.homePath() : '/login') },

  { path: '/login', name: 'login', component: LoginView },
  { path: '/register', name: 'register', component: RegisterView },

  // Any logged-in user (trekker, staff or admin) can edit their own profile.
  { path: '/profile', name: 'profile', component: ProfileView, meta: { requiresAuth: true } },

  // --- admin ---
  {
    path: '/admin',
    name: 'admin-dashboard',
    component: AdminDashboard,
    meta: { requiresAuth: true, role: 'admin' },
  },
  {
    path: '/admin/treks',
    name: 'admin-treks',
    component: AdminTreks,
    meta: { requiresAuth: true, role: 'admin' },
  },
  {
    path: '/admin/staff',
    name: 'admin-staff',
    component: AdminStaff,
    meta: { requiresAuth: true, role: 'admin' },
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: AdminUsers,
    meta: { requiresAuth: true, role: 'admin' },
  },
  {
    path: '/admin/bookings',
    name: 'admin-bookings',
    component: AdminBookings,
    meta: { requiresAuth: true, role: 'admin' },
  },

  // --- staff ---
  {
    path: '/staff',
    name: 'staff-dashboard',
    component: StaffDashboard,
    meta: { requiresAuth: true, role: 'staff' },
  },
  {
    // :id is read inside the view as this.$route.params.id
    path: '/staff/treks/:id/participants',
    name: 'staff-participants',
    component: StaffParticipants,
    meta: { requiresAuth: true, role: 'staff' },
  },

  // --- trekker ---
  {
    path: '/treks',
    name: 'treks',
    component: BrowseTreks,
    meta: { requiresAuth: true, role: 'user' },
  },
  {
    path: '/bookings',
    name: 'my-bookings',
    component: MyBookings,
    meta: { requiresAuth: true, role: 'user' },
  },

  // Anything unmatched.
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

/**
 * The guard. It runs before EVERY navigation, so it is the one place that
 * enforces "a trekker cannot open an admin page".
 *
 * Returning a location object cancels the navigation and redirects instead;
 * returning nothing lets it continue.
 */
router.beforeEach((to) => {
  const loggedIn = !!store.token

  // Not logged in but asking for a protected page -> go and log in.
  if (to.meta.requiresAuth && !loggedIn) {
    return { name: 'login' }
  }

  // Logged in but asking for the wrong role's page -> send to your own home.
  if (to.meta.role && !store.hasRole(to.meta.role)) {
    const home = store.homePath()
    // If "home" is the very page we are refusing, the account holds no usable
    // role at all. Redirecting there would loop forever, so treat it as logged
    // out instead.
    if (home === to.path) {
      store.logout()
      return { name: 'login' }
    }
    return home
  }

  // Already logged in, so the login/register pages are pointless.
  if (loggedIn && (to.name === 'login' || to.name === 'register')) {
    return store.homePath()
  }
})

export default router
