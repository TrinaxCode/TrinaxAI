import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const realBackend = process.env.TRINAXAI_E2E_REAL === '1';
const pwaPort = process.env.TRINAXAI_E2E_PORT || '4174';
const ragPort = process.env.TRINAXAI_E2E_RAG_PORT || '3333';
const repoRoot = path.resolve(process.cwd(), '..');
const venvPython = path.join(repoRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.TRINAXAI_PYTHON
  || (fs.existsSync(venvPython) ? venvPython : process.platform === 'win32' ? 'python' : 'python3');
const realStorage = realBackend ? fs.mkdtempSync(path.join(os.tmpdir(), 'trinaxai-e2e-real-')) : '';
const proxySecret = 'trinaxai-e2e-real';
const shellQuote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;

const gatewayServer = {
  command: `TRINAXAI_PWA_DIST=.e2e-dist-${pwaPort} npm run build && CI=true TRINAXAI_PWA_DIST=.e2e-dist-${pwaPort} TRINAXAI_PWA_HOST=127.0.0.1 TRINAXAI_PWA_PORT=${pwaPort} TRINAXAI_RAG_TARGET=http://127.0.0.1:${ragPort} VITE_TRINAXAI_RAG_TARGET=http://127.0.0.1:${ragPort} TRINAXAI_PROXY_SECRET=${shellQuote(proxySecret)} npm run serve`,
  url: `http://127.0.0.1:${pwaPort}`,
  reuseExistingServer: false,
  timeout: 120_000,
};

const backendServer = {
  command: [
    `PYTHONPATH=${shellQuote(repoRoot)}`,
    `TRINAXAI_PERSIST_DIR=${shellQuote(realStorage)}`,
    `TRINAXAI_INDEX_DIR=${shellQuote(realStorage)}`,
    `TRINAXAI_INFERENCE_LOCK_FILE=${shellQuote(path.join(realStorage, '.inference.lock'))}`,
    `TRINAXAI_PROXY_SECRET=${shellQuote(proxySecret)}`,
    `TRINAXAI_CORS_ORIGINS=${shellQuote(`http://127.0.0.1:${pwaPort}`)}`,
    `${shellQuote(python)} -m uvicorn app.main:app --host 127.0.0.1 --port ${ragPort}`,
  ].join(' '),
  url: `http://127.0.0.1:${ragPort}/health`,
  reuseExistingServer: false,
  timeout: 120_000,
};

export default defineConfig({
  testDir: './e2e',
  globalTeardown: './e2e/global-teardown.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${pwaPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: {
        ...devices['Desktop Chrome'],
        permissions: ['microphone'],
        launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--host-resolver-rules=MAP trinaxai.test 127.0.0.1'] },
      },
    },
    { name: 'chromium-tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, launchOptions: { args: ['--host-resolver-rules=MAP trinaxai.test 127.0.0.1'] } } },
    { name: 'chromium-mobile', use: { ...devices['Pixel 7'], launchOptions: { args: ['--host-resolver-rules=MAP trinaxai.test 127.0.0.1'] } } },
  ],
  webServer: realBackend ? [backendServer, gatewayServer] : gatewayServer,
});
