/**
 * Vite Config.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  base: mode === 'development' ? '/' : '/frontend-dist/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
}))
