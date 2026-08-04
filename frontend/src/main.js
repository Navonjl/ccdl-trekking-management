/**
 * Entry point. Vite loads this from index.html.
 *
 * Bootstrap is the only styling framework used in this project (the spec allows
 * no other). The CSS is imported here so it applies to every component; the JS
 * bundle is imported because the responsive navbar toggle needs it. Importing
 * them here rather than from a CDN means npm pins the version for us.
 */
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
