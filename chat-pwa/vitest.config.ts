import { configDefaults, defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    testTimeout: 30_000,
    hookTimeout: 30_000,
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    clearMocks: true,
    css: true,
    exclude: [...configDefaults.exclude, 'e2e/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      // The PWA entrypoint imports Vite's virtual service-worker module and is
      // covered by the production build/E2E gates, not V8 unit remapping.
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx'],
      // Keep the measured baseline from regressing while the untested UI is retired.
      thresholds: {
        statements: 60,
        lines: 60,
        functions: 55,
        branches: 64,
      },
    },
  },
});
