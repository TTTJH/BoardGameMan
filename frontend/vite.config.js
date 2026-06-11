import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/covers': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/rule-pages': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/visual-refs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/game-assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
