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
        ws: true,   // WebSocket proxy for /api/training/stream
      },
    },
  },
  build: {
    outDir: '../src/api/static',  // served by FastAPI in production
    chunkSizeWarningLimit: 6000,
    rollupOptions: {
      output: {
        manualChunks: {
          plotly:   ['plotly.js-dist-min'],
          recharts: ['recharts'],
          react:    ['react', 'react-dom'],
        },
      },
    },
  },
})
