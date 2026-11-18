import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Port 3000 matches the backend's default CORS_ORIGINS.
  server: { port: 3000 },
  preview: { port: 3000 },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
    css: false,
  },
});
