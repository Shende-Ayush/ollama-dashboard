import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendUrl = process.env.VITE_API_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward API calls to the backend during dev
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
