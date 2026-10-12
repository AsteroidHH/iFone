import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const backend = process.env.QUORUM_BACKEND ?? 'http://localhost:8000';

const csp = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'quorum-csp',
      apply: 'build',
      transformIndexHtml: (html) =>
        html.replace('<head>', `<head>\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />\n    <meta name="referrer" content="no-referrer" />`),
    },
  ],
  build: {
    assetsInlineLimit: 0,
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
