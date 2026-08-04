import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],

  resolve: {
    // "@" is a shortcut for the src folder, so imports never need ../../ chains.
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    port: 5173,

    // WHY THIS PROXY EXISTS:
    // The Vue dev server runs on port 5173 and Flask runs on port 5000. To a
    // browser those are two DIFFERENT origins, so calling
    // fetch('http://localhost:5000/api/...') straight from the page would be a
    // cross-origin request and the browser would block reading the response
    // unless Flask replied with CORS headers.
    //
    // Instead every request in this app uses a relative URL ("/api/..."), which
    // goes to localhost:5173. Vite then forwards it to Flask itself, server to
    // server, where the browser's same-origin policy does not apply. Because the
    // browser only ever talks to one origin, every request IS same-origin, so
    // the spec-forbidden flask-cors package is not needed anywhere.
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
