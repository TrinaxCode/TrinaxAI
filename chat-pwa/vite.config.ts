import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { execFile, spawn } from 'child_process';
import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');
const certKey = path.join(__dirname, 'certs', 'localhost-key.pem');
const certFile = path.join(__dirname, 'certs', 'localhost.pem');
const certPfx = path.join(__dirname, 'certs', 'trinaxai-local.pfx');
const pfxPassphrase = process.env.TRINAXAI_CERT_PASSPHRASE || 'trinaxai-local';
const httpsConfig = fs.existsSync(certPfx)
  ? { pfx: fs.readFileSync(certPfx), passphrase: pfxPassphrase }
  : fs.existsSync(certKey) && fs.existsSync(certFile)
    ? { key: fs.readFileSync(certKey), cert: fs.readFileSync(certFile) }
    : undefined;

function env(name: string, fallback: string): string {
  return process.env[name] || fallback;
}

function userHome(): string {
  return process.env.TRINAXAI_HOME
    || process.env.HOME
    || process.env.USERPROFILE
    || (process.env.HOMEPATH && process.env.HOMEDRIVE
      ? path.join(process.env.HOMEDRIVE || '', process.env.HOMEPATH || '')
      : repoRoot);
}

function localPython(): string {
  const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
  const venvPythonWindows = path.join(repoRoot, '.venv', 'Scripts', 'python.exe');
  if (process.env.TRINAXAI_PYTHON) return process.env.TRINAXAI_PYTHON;
  if (fs.existsSync(venvPython)) return venvPython;
  if (fs.existsSync(venvPythonWindows)) return venvPythonWindows;
  return process.platform === 'win32' ? 'python' : 'python3';
}

function spawnManager(action: string): void {
  const child = spawn(localPython(), [path.join(repoRoot, 'service_manager.py'), action, '--base-dir', repoRoot], {
    cwd: repoRoot,
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });
  child.unref();
}

function postReload(ragTarget: string): void {
  const url = new URL('/system/reload', ragTarget);
  const requestOptions = {
    hostname: url.hostname,
    port: url.port,
    path: url.pathname,
    method: 'POST',
    rejectUnauthorized: false,
    family: 4,
  };
  const client = url.protocol === 'https:' ? https : http;
  const req = client.request(requestOptions, () => {});
  req.on('error', () => {});
  req.end();
}

function proxyConfig() {
  return {
    '/api/rag': {
      target: env('TRINAXAI_RAG_TARGET', env('VITE_TRINAXAI_RAG_TARGET', 'http://127.0.0.1:3333')),
      changeOrigin: true,
      secure: false,
      xfwd: true,
      rewrite: (proxyPath: string) => proxyPath.replace(/^\/api\/rag/, ''),
    },
    '/api/ollama': {
      target: env('TRINAXAI_OLLAMA_TARGET', 'http://127.0.0.1:11434'),
      changeOrigin: true,
      secure: false,
      xfwd: true,
      headers: { Origin: env('TRINAXAI_OLLAMA_TARGET', 'http://127.0.0.1:11434') },
      rewrite: (proxyPath: string) => proxyPath.replace(/^\/api\/ollama/, ''),
    },
  };
}

function installSystemControl(server: any): void {
  const ragTarget = env('TRINAXAI_RAG_TARGET', env('VITE_TRINAXAI_RAG_TARGET', 'http://127.0.0.1:3333'));
  const allowLanSystem = ['1', 'true', 'yes', 'on'].includes((process.env.TRINAXAI_ALLOW_LAN_SYSTEM || '').toLowerCase());
  const isLoopback = (host: string): boolean => {
    const clean = host.replace(/^::ffff:/, '');
    if (['127.0.0.1', '::1', 'localhost'].includes(clean)) return true;
    if (net.isIP(clean) === 0) return false;
    return clean.startsWith('127.');
  };
  const isPrivateLan = (host: string): boolean => {
    const clean = host.replace(/^::ffff:/, '');
    if (isLoopback(clean)) return true;
    if (net.isIP(clean) === 0) return false;
    if (clean.startsWith('10.') || clean.startsWith('192.168.')) return true;
    const parts = clean.split('.').map((part) => Number(part));
    if (parts.length === 4 && parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
    // IPv6 link-local (fe80::/10) — common on Windows dual-stack networks
    if (net.isIPv6(clean) && clean.startsWith('fe80:')) return true;
    // IPv6 unique local (fc00::/7 fd00::/8)
    if (net.isIPv6(clean) && (clean.startsWith('fd') || clean.startsWith('fc'))) return true;
    return false;
  };
  server.middlewares.use('/api/system', async (req: any, res: any) => {
    if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
    const token = req.headers['x-admin-token'] as string | undefined;
    const adminToken = process.env.TRINAXAI_ADMIN_TOKEN;
    const peer = req.socket?.remoteAddress || '127.0.0.1';
    const authorized = (adminToken && token === adminToken) || isLoopback(peer) || (allowLanSystem && isPrivateLan(peer));
    if (!authorized) {
      res.statusCode = 403;
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ ok: false, error: 'Operación no autorizada. Activa LAN system control o usa X-Admin-Token.' }));
      return;
    }
    const url = new URL(req.url || '/', 'http://localhost');
    const action = url.pathname.replace(/^\/+/, '');
    const sendJson = (status: number, body: unknown) => {
      res.statusCode = status;
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(body));
    };
    if (action === 'shutdown' || action === 'startup' || action === 'stop-all') {
      const managerAction = action === 'startup' ? 'start-ai' : action === 'shutdown' ? 'stop-ai' : 'stop-all';
      if (action === 'stop-all') {
        sendJson(200, { ok: true, output: 'Full TrinaxAI shutdown initiated.' });
        setTimeout(() => spawnManager(managerAction), 250);
        return;
      }
      if (action === 'shutdown') {
        sendJson(200, { ok: true, output: 'AI shutdown initiated. The PWA remains available for restart.' });
        setTimeout(() => spawnManager(managerAction), 50);
        return;
      }
      execFile(localPython(), [path.join(repoRoot, 'service_manager.py'), managerAction, '--base-dir', repoRoot], { windowsHide: true }, (err, stdout, stderr) => {
        sendJson(err ? 500 : 200, { ok: !err, output: stdout, error: stderr || (err?.message ?? '') });
      });
    } else if (action === 'index') {
      const dir = url.searchParams.get('dir') || env('TRINAXAI_INDEX_DIR', path.join(userHome(), 'Documents'));
      execFile(localPython(), [path.join(repoRoot, 'index.py')], {
        timeout: 600000,
        env: { ...process.env, TRINAXAI_INDEX_DIR: dir },
        windowsHide: true,
      }, (err, stdout, stderr) => {
        if (!err) postReload(ragTarget);
        sendJson(err ? 500 : 200, { ok: !err, output: stdout, error: stderr || (err?.message ?? '') });
      });
    } else if (action === 'reload') {
      const reloadUrl = new URL('/system/reload', ragTarget);
      const client = reloadUrl.protocol === 'https:' ? https : http;
      const req = client.request({ hostname: reloadUrl.hostname, port: reloadUrl.port, path: reloadUrl.pathname, method: 'POST', rejectUnauthorized: false }, (ragRes: any) => {
        let body = '';
        ragRes.on('data', (d: string) => body += d);
        ragRes.on('end', () => {
          res.setHeader('Content-Type', 'application/json');
          res.end(body || JSON.stringify({ ok: true }));
        });
      });
      req.on('error', (e: Error) => sendJson(502, { ok: false, error: e.message }));
      req.end();
    } else {
      sendJson(404, { ok: false, error: `Unknown action: ${action}` });
    }
  });
}

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: [
        'favicon.ico',
        'favicon-16x16.png',
        'favicon-32x32.png',
        'apple-touch-icon.png',
        'android-chrome-192x192.png',
        'android-chrome-512x512.png',
        'logo-of-app.webp',
        'logo-for-ai.webp',
        'logo-for-user.webp',
        'new-logo-for-AI.webp',
        'new-logo-for-user.webp',
        'offline.html',
      ],
      manifest: {
        id: '/',
        name: 'TrinaxAI Chat',
        short_name: 'TrinaxAI',
        description: 'TrinaxAI — Ollama & RAG at your fingertips.',
        dir: 'ltr',
        lang: 'es',
        categories: ['productivity', 'utilities'],
        theme_color: '#000000',
        background_color: '#000000',
        display: 'fullscreen',
        display_override: ['fullscreen', 'standalone', 'minimal-ui'],
        orientation: 'portrait-primary',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/apple-touch-icon.png',
            sizes: '180x180',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/android-chrome-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any maskable',
          },
          {
            src: '/android-chrome-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
        shortcuts: [
          {
            name: 'New Chat',
            short_name: 'Chat',
            description: 'Start a new chat session',
            url: '/',
            icons: [{ src: '/android-chrome-192x192.png', sizes: '192x192' }],
          },
          {
            name: 'Settings',
            short_name: 'Settings',
            description: 'Open app settings',
            url: '/#settings',
            icons: [{ src: '/android-chrome-192x192.png', sizes: '192x192' }],
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,webp,svg,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            // Cache static assets (JS, CSS) with CacheFirst for instant reloads
            urlPattern: /\.(?:js|css)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-resources',
              expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 },
            },
          },
          {
            // Cache images locally served
            urlPattern: /\.(?:png|webp|ico|svg)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 24 * 60 * 60 },
            },
          },
          {
            // Google Fonts stylesheets
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'google-fonts-stylesheets',
              expiration: { maxEntries: 5, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          {
            // Google Fonts webfont files
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-webfonts',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          {
            // Read-only API calls (collections, sources, memory, health) — NetworkFirst
            urlPattern: /\/api\/(rag|ollama)\/(collections|sources|chunks|memory|health|tags)/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-readonly',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 50, maxAgeSeconds: 5 * 60 },
            },
          },
          {
            // System/reload endpoint
            urlPattern: /\/api\/system\/reload/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-system',
              expiration: { maxEntries: 5, maxAgeSeconds: 60 },
            },
          },
        ],
      },
    }),
    {
      name: 'trinaxai-system-control',
      configureServer: installSystemControl,
      configurePreviewServer: installSystemControl,
    },
  ],
  server: {
    https: httpsConfig,
    host: '0.0.0.0',
    port: 3334,
    proxy: proxyConfig(),
  },
  preview: {
    https: httpsConfig,
    host: '0.0.0.0',
    port: 3334,
    proxy: proxyConfig(),
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          motion: ['framer-motion'],
          markdown: ['react-markdown'],
          icons: ['react-icons/md', 'react-icons/fa'],
        },
      },
    },
  },
});
