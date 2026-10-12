import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const backend = process.env.QUORUM_BACKEND ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: { cytoscape: ['cytoscape'], vendor: ['react', 'react-dom', 'zustand', '@tanstack/react-query', 'zod'] },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: backend, changeOrigin: false } },
  },
  preview: {
    port: 5173,
    proxy: { '/api': { target: backend, changeOrigin: false } },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
