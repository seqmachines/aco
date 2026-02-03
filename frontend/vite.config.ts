import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/intake': { target: 'http://localhost:8000', changeOrigin: true },
      '/scan': { target: 'http://localhost:8000', changeOrigin: true },
      '/manifest': { target: 'http://localhost:8000', changeOrigin: true },
      '/understanding': { target: 'http://localhost:8000', changeOrigin: true },
      '/scripts': { target: 'http://localhost:8000', changeOrigin: true },
      '/notebooks': { target: 'http://localhost:8000', changeOrigin: true },
      '/reports': { target: 'http://localhost:8000', changeOrigin: true },
      '/runs': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
