import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const rootDir = fileURLToPath(new URL('.', import.meta.url))
const require = createRequire(import.meta.url)

function resolveFromFrontend() {
  return {
    name: 'resolve-from-frontend',
    enforce: 'pre' as const,
    resolveId(id: string, importer?: string) {
      if (!importer?.replaceAll('\\', '/').includes('/tests/unit/frontend/')) {
        return null
      }
      if (id.startsWith('.') || id.startsWith('/') || path.isAbsolute(id) || id.startsWith('@/')) {
        return null
      }
      if (id === 'vitest' || id.startsWith('vitest/') || id.startsWith('@vitest/')) {
        return null
      }
      try {
        return require.resolve(id, { paths: [rootDir] })
      } catch {
        return null
      }
    },
  }
}

export default defineConfig({
  plugins: [resolveFromFrontend(), react(), tailwindcss()],
  resolve: {
    alias: [{ find: /^@\//, replacement: `${path.resolve(rootDir, 'src')}/` }],
  },
  server: {
    fs: {
      allow: [path.resolve(rootDir, '../..')],
    },
  },
  test: {
    environment: 'jsdom',
    include: ['../../tests/unit/frontend/**/*.{test,spec}.{ts,tsx}'],
    setupFiles: ['./src/test-setup.ts'],
  },
})
