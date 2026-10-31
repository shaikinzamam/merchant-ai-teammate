import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api/* is proxied to the FastAPI backend, so no CORS setup is needed in development.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: 'http://localhost:8001', rewrite: p => p.replace(/^\/api/, '') } } },
})
