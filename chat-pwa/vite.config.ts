import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { execFile, spawn } from 'child_process';
import { createHmac, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  isAllowedOllamaProxyRequest,
  isAuthorizedScopedProxyPeer,
  isAuthorizedSystemProxyPeer,
  deviceTokenHasScope,
  isLoopbackAddress,
  isPrivateLanAddress,
  normalizeAddress,
} from './vite-security';
import { acquireInferenceProcessLock } from './inference-lock';
import { PWA_SECURITY_HEADERS } from './security-headers';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');
const certKey = path.join(__dirname, 'certs', 'localhost-key.pem');
const certFile = path.join(__dirname, 'certs', 'localhost.pem');
const certPfx = path.join(__dirname, 'certs', 'trinaxai-local.pfx');
const pfxPassphrase = process.env.TRINAXAI_CERT_PASSPHRASE || 'trinaxai-local';
const localCa = fs.existsSync(certFile) ? fs.readFileSync(certFile) : undefined;
const httpsConfig = process.env.CI === 'true'
  ? undefined
  : fs.existsSync(certPfx)
  ? { pfx: fs.readFileSync(certPfx), passphrase: pfxPassphrase }
  : fs.existsSync(certKey) && fs.existsSync(certFile)
    ? { key: fs.readFileSync(certKey), cert: fs.readFileSync(certFile) }
    : undefined;

function env(name: string, fallback: string): string {
  return process.env[name] || fallback;
}

const PROXY_IDENTITY_HEADERS = [
  'x-trinaxai-proxy',
  'x-trinaxai-client-ip',
  'x-trinaxai-proxy-timestamp',
  'x-trinaxai-proxy-nonce',
  'x-trinaxai-proxy-signature',
] as const;

let proxySecretCache: string | undefined;
const ollamaRateBuckets = new Map<string, { tokens: number; updatedAt: number }>();

function deviceRegistryPath(): string {
  const configured = process.env.TRINAXAI_DEVICE_REGISTRY;
  return configured
    ? (path.isAbsolute(configured) ? configured : path.resolve(repoRoot, configured))
    : path.join(repoRoot, 'storage', 'device_pairing.json');
}

function deviceSecretPath(): string {
  const configured = process.env.TRINAXAI_DEVICE_SECRET_FILE;
  return configured
    ? (path.isAbsolute(configured) ? configured : path.resolve(repoRoot, configured))
    : path.join(repoRoot, 'storage', '.device_secret');
}

function pairedDeviceGrants(token: string, scope: string): boolean {
  if (!token) return false;
  try {
    const registryFile = deviceRegistryPath();
    const secretFile = deviceSecretPath();
    const readBounded = (file: string, maxBytes: number, encoding: BufferEncoding): string => {
      const descriptor = fs.openSync(file, 'r');
      try {
        const stat = fs.fstatSync(descriptor);
        if (!stat.isFile() || stat.size > maxBytes) throw new Error('invalid device credential file');
        return fs.readFileSync(descriptor, encoding);
      } finally {
        fs.closeSync(descriptor);
      }
    };
    const registry = JSON.parse(readBounded(registryFile, 1024 * 1024, 'utf8')) as unknown;
    const secret = readBounded(secretFile, 4096, 'ascii').trim();
    try { fs.chmodSync(registryFile, 0o600); fs.chmodSync(secretFile, 0o600); } catch { /* best effort */ }
    return deviceTokenHasScope(token, scope, registry, secret);
  } catch {
    return false;
  }
}

function proxySecret(): string {
  if (proxySecretCache !== undefined) return proxySecretCache;
  const configured = (process.env.TRINAXAI_PROXY_SECRET || '').trim();
  if (configured) {
    proxySecretCache = configured;
    return proxySecretCache;
  }

  const secretPath = process.env.TRINAXAI_PROXY_SECRET_FILE
    ? path.resolve(process.env.TRINAXAI_PROXY_SECRET_FILE)
    : path.join(repoRoot, 'storage', '.proxy_secret');
  try {
    proxySecretCache = fs.readFileSync(secretPath, 'utf8').trim();
    try { fs.chmodSync(secretPath, 0o600); } catch { /* best effort on Windows/read-only stores */ }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      proxySecretCache = '';
      return proxySecretCache;
    }
    const generated = randomBytes(32).toString('hex');
    try {
      fs.mkdirSync(path.dirname(secretPath), { recursive: true });
      fs.writeFileSync(secretPath, generated, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
      proxySecretCache = generated;
    } catch (writeError) {
      if ((writeError as NodeJS.ErrnoException).code === 'EEXIST') {
        try {
          proxySecretCache = fs.readFileSync(secretPath, 'utf8').trim();
          try { fs.chmodSync(secretPath, 0o600); } catch { /* best effort */ }
        } catch { proxySecretCache = ''; }
      } else {
        proxySecretCache = '';
      }
    }
  }
  return proxySecretCache || '';
}

function signProxyIdentity(
  secret: string,
  clientIp: string,
  timestamp: string,
  nonce: string,
  method: string,
  pathname: string,
): string {
  const payload = ['v1', clientIp, timestamp, nonce, method.toUpperCase(), pathname].join('\n');
  return createHmac('sha256', secret).update(payload, 'utf8').digest('hex');
}

function attachSignedProxyIdentity(proxyReq: any, req: any): void {
  for (const header of PROXY_IDENTITY_HEADERS) proxyReq.removeHeader(header);
  const secret = proxySecret();
  if (!secret) return;
  const clientIp = normalizeAddress(req.socket?.remoteAddress || 'unknown');
  if (net.isIP(clientIp) === 0) return;
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = randomBytes(16).toString('hex');
  const pathname = new URL(String(proxyReq.path || '/'), 'http://localhost').pathname;
  const signature = signProxyIdentity(secret, clientIp, timestamp, nonce, req.method || 'GET', pathname);
  proxyReq.setHeader('X-TrinaxAI-Proxy', 'v1');
  proxyReq.setHeader('X-TrinaxAI-Client-IP', clientIp);
  proxyReq.setHeader('X-TrinaxAI-Proxy-Timestamp', timestamp);
  proxyReq.setHeader('X-TrinaxAI-Proxy-Nonce', nonce);
  proxyReq.setHeader('X-TrinaxAI-Proxy-Signature', signature);
}

function sendProxyError(res: any, status: number, error: string): void {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify({ ok: false, error }));
}

function ollamaProxyRateLimit(): number {
  const configured = Number(process.env.TRINAXAI_OLLAMA_PROXY_RATE_LIMIT || 30);
  return Number.isFinite(configured) ? Math.max(1, Math.floor(configured)) : 30;
}

function ollamaRateAllowed(peer: string): boolean {
  const max = ollamaProxyRateLimit();
  const now = Date.now();
  const previous = ollamaRateBuckets.get(peer) || { tokens: max, updatedAt: now };
  const tokens = Math.min(max, previous.tokens + ((now - previous.updatedAt) * max / 60_000));
  if (tokens < 1) {
    ollamaRateBuckets.set(peer, { tokens, updatedAt: now });
    return false;
  }
  if (!ollamaRateBuckets.has(peer) && ollamaRateBuckets.size >= 2000) {
    const oldest = [...ollamaRateBuckets.entries()]
      .sort((left, right) => left[1].updatedAt - right[1].updatedAt)[0]?.[0];
    if (oldest) ollamaRateBuckets.delete(oldest);
  }
  ollamaRateBuckets.set(peer, { tokens: tokens - 1, updatedAt: now });
  return true;
}

function installProxyBoundary(server: any): void {
  server.middlewares.use((req: any, res: any, next: () => void) => {
    const pathname = new URL(req.url || '/', 'http://localhost').pathname;
    if (!pathname.startsWith('/api/rag') && !pathname.startsWith('/api/ollama')) {
      next();
      return;
    }

    // A browser must never be able to supply the gateway-only identity headers.
    for (const header of PROXY_IDENTITY_HEADERS) delete req.headers[header];
    const peer = normalizeAddress(req.socket?.remoteAddress || 'unknown');

    if (pathname.startsWith('/api/rag')) {
      if (!isLoopbackAddress(peer) && !proxySecret()) {
        sendProxyError(res, 503, 'Trusted RAG proxy identity is unavailable.');
        return;
      }
      next();
      return;
    }

    if (!isAllowedOllamaProxyRequest(req.method || 'GET', pathname)) {
      sendProxyError(res, 404, 'Ollama operation is not exposed by TrinaxAI.');
      return;
    }
    const suppliedToken = String(req.headers['x-admin-token'] || '');
    const deviceToken = String(req.headers['x-trinaxai-device-token'] || '');
    const adminToken = process.env.TRINAXAI_ADMIN_TOKEN || '';
    const requiredScope = pathname === '/api/ollama/api/pull' ? 'system' : 'chat';
    const authorized = (requiredScope === 'chat' && isPrivateLanAddress(peer)) || isAuthorizedScopedProxyPeer(
      peer,
      suppliedToken,
      adminToken,
      deviceToken,
      pairedDeviceGrants(deviceToken, requiredScope),
    );
    if (!authorized) {
      sendProxyError(res, 403, `Ollama access requires a paired ${requiredScope} device or administrator.`);
      return;
    }
    // Ollama has no use for TrinaxAI's credential; do not forward it.
    delete req.headers['x-admin-token'];
    delete req.headers['x-trinaxai-device-token'];
    if (!ollamaRateAllowed(peer)) {
      res.setHeader('Retry-After', String(Math.max(1, Math.ceil(60 / ollamaProxyRateLimit()))));
      sendProxyError(res, 429, 'Too many Ollama requests.');
      return;
    }
    const lockDir = process.env.TRINAXAI_INFERENCE_LOCK_FILE
      ? path.resolve(process.env.TRINAXAI_INFERENCE_LOCK_FILE)
      : path.join(repoRoot, 'storage', '.inference.lock');
    const timeoutMs = Math.max(
      1_000,
      Number(process.env.TRINAXAI_INFERENCE_QUEUE_TIMEOUT || 600) * 1_000,
    );
    void acquireInferenceProcessLock(lockDir, { timeoutMs }).then((release) => {
      if (req.destroyed || res.writableEnded) {
        release();
        return;
      }
      let released = false;
      const releaseOnce = () => {
        if (released) return;
        released = true;
        release();
      };
      res.once('finish', releaseOnce);
      res.once('close', releaseOnce);
      next();
    }).catch(() => {
      res.setHeader('Retry-After', String(Math.ceil(timeoutMs / 1000)));
      sendProxyError(res, 503, 'Local inference queue timed out.');
    });
  });
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
    ...(url.protocol === 'https:' && isLoopbackAddress(url.hostname) && localCa ? { ca: localCa } : {}),
    family: 4,
  };
  const client = url.protocol === 'https:' ? https : http;
  const req = client.request(requestOptions, () => {});
  req.on('error', () => {});
  req.end();
}

function proxyConfig() {
  const ragTarget = env('TRINAXAI_RAG_TARGET', env('VITE_TRINAXAI_RAG_TARGET', 'http://127.0.0.1:3333'));
  const ollamaTarget = env('TRINAXAI_OLLAMA_TARGET', 'http://127.0.0.1:11434');
  const trustedAgent = (target: string) => {
    const url = new URL(target);
    return url.protocol === 'https:' && isLoopbackAddress(url.hostname) && localCa
      ? new https.Agent({ ca: localCa })
      : undefined;
  };
  const verifyTls = (target: string) => {
    const url = new URL(target);
    // The local API may use a private development CA that Node does not load.
    // This exception is limited to an explicit loopback target; every remote
    // HTTPS proxy target continues to require normal certificate validation.
    return url.protocol !== 'https:' || !isLoopbackAddress(url.hostname);
  };
  return {
    '/api/rag': {
      target: ragTarget,
      agent: trustedAgent(ragTarget),
      changeOrigin: true,
      secure: verifyTls(ragTarget),
      xfwd: false,
      rewrite: (proxyPath: string) => proxyPath.replace(/^\/api\/rag/, ''),
      configure: (proxy: any) => {
        proxy.on('proxyReq', attachSignedProxyIdentity);
      },
    },
    '/api/ollama': {
      target: ollamaTarget,
      agent: trustedAgent(ollamaTarget),
      changeOrigin: true,
      secure: verifyTls(ollamaTarget),
      xfwd: false,
      headers: { Origin: ollamaTarget },
      rewrite: (proxyPath: string) => proxyPath.replace(/^\/api\/ollama/, ''),
    },
  };
}

function installSystemControl(server: any): void {
  const ragTarget = env('TRINAXAI_RAG_TARGET', env('VITE_TRINAXAI_RAG_TARGET', 'http://127.0.0.1:3333'));
  const allowLanSystem = ['1', 'true', 'yes', 'on'].includes((process.env.TRINAXAI_ALLOW_LAN_SYSTEM || '').toLowerCase());
  server.middlewares.use('/api/system', async (req: any, res: any) => {
    if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
    const token = req.headers['x-admin-token'] as string | undefined;
    const deviceToken = String(req.headers['x-trinaxai-device-token'] || '');
    const adminToken = process.env.TRINAXAI_ADMIN_TOKEN;
    const peer = req.socket?.remoteAddress || '127.0.0.1';
    const origin = String(req.headers.origin || '');
    const trustedBrowserOrigin = !origin || (() => {
      try {
        const parsed = new URL(origin);
        return ['3334', '3335'].includes(parsed.port) && isPrivateLanAddress(parsed.hostname);
      } catch {
        return false;
      }
    })();
    const scopedAuthorized = isAuthorizedScopedProxyPeer(
      peer,
      token || '',
      adminToken || '',
      deviceToken,
      pairedDeviceGrants(deviceToken, 'system'),
    );
    const legacyLanAuthorized = !token && !deviceToken && isAuthorizedSystemProxyPeer(
      peer,
      '',
      adminToken || '',
      allowLanSystem,
    );
    const authorized = trustedBrowserOrigin && (scopedAuthorized || legacyLanAuthorized);
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
      const req = client.request({
        hostname: reloadUrl.hostname,
        port: reloadUrl.port,
        path: reloadUrl.pathname,
        method: 'POST',
        ...(reloadUrl.protocol === 'https:' && isLoopbackAddress(reloadUrl.hostname) && localCa ? { ca: localCa } : {}),
      }, (ragRes: any) => {
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
      // Keep an update waiting until the person explicitly applies it. Reloading
      // a chat automatically can interrupt a streamed answer or lose a draft.
      registerType: 'prompt',
      includeAssets: [
        'favicon.svg',
        'favicon-96x96.png',
        'favicon.ico',
        'apple-touch-icon.png',
        'web-app-manifest-192x192.png',
        'web-app-manifest-512x512.png',
        'logo-of-app.webp',
        'logo-for-ai.webp',
        'new-logo-for-AI.webp',
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
        display: 'standalone',
        display_override: ['window-controls-overlay', 'standalone', 'minimal-ui'],
        orientation: 'any',
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
            src: '/web-app-manifest-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any maskable',
          },
          {
            src: '/web-app-manifest-512x512.png',
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
            icons: [{ src: '/web-app-manifest-192x192.png', sizes: '192x192' }],
          },
          {
            name: 'Settings',
            short_name: 'Settings',
            description: 'Open app settings',
            url: '/#settings',
            icons: [{ src: '/web-app-manifest-192x192.png', sizes: '192x192' }],
          },
        ],
      },
      workbox: {
        cleanupOutdatedCaches: true,
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
            // Cache only harmless service metadata. RAG sources, chunks and
            // memories can contain private local information and must always
            // come from the backend rather than remain in a browser cache.
            urlPattern: /\/api\/rag\/health/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-metadata',
              networkTimeoutSeconds: 3,
              expiration: { maxEntries: 10, maxAgeSeconds: 60 },
            },
          },
        ],
      },
    }),
    {
      name: 'trinaxai-proxy-boundary',
      configureServer: installProxyBoundary,
      configurePreviewServer: installProxyBoundary,
    },
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
    headers: PWA_SECURITY_HEADERS,
    proxy: proxyConfig(),
  },
  preview: {
    https: httpsConfig,
    host: '0.0.0.0',
    port: 3334,
    headers: PWA_SECURITY_HEADERS,
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
