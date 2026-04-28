import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendUrl = process.env.VITE_API_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
      interval: 1,
    },
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    },
  },
});