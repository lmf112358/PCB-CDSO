import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API calls to the FastAPI service during local dev.
      // In docker-compose, nginx serves both so this is dev-only.
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/projects': { target: 'http://localhost:8000', changeOrigin: true },
      '/tasks': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    css: true,
  },
})
