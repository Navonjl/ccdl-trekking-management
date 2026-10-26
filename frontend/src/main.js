/**
 * Entry point. Vite loads this from index.html.
 *
 * Styling is Bootstrap, compiled from Sass in styles/main.scss with the Head in
 * the Clouds palette, plus the Nunito font. Both are imported here so they apply
 * to every component; the Bootstrap JS bundle is imported because the
 * responsive navbar toggle needs it. Importing them here rather than from a CDN
 * means npm pins the versions for us.
 */
import '@fontsource-variable/nunito'
import './styles/main.scss'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
