import { execFile, spawn } from 'node:child_process';
import { createHmac, randomBytes, X509Certificate } from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { acquireInferenceProcessLock } from './server-dist/inference-lock.js';
import { PWA_SECURITY_HEADERS } from './server-dist/security-headers.js';
import {
  deviceTokenHasScope,
  isAllowedOllamaProxyRequest,
  isAuthorizedScopedProxyPeer,
  isAuthorizedSystemProxyPeer,
  isLoopbackAddress,
  isPrivateLanAddress,
  normalizeAddress,
  needsInferenceLock,
  requiredOllamaProxyScope,
  requiredRagProxyScope,
  deviceTokenFromCookie,
} from './server-dist/vite-security.js';

const appDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(appDir, '..');
const configuredDist = process.env.TRINAXAI_PWA_DIST;
const distDir = configuredDist
  ? path.resolve(appDir, configuredDist)
  : path.join(appDir, 'dist');
const certDir = path.join(appDir, 'certs');
const localCaPath = path.join(certDir, 'localhost.pem');
const localCaCandidates = [
  process.env.TRINAXAI_LOCAL_CA_FILE,
  path.join(certDir, 'rootCA.pem'),
  process.platform === 'win32'
    ? path.join(process.env.LOCALAPPDATA || '', 'mkcert', 'rootCA.pem')
    : process.platform === 'darwin'
      ? path.join(os.homedir(), 'Library', 'Application Support', 'mkcert', 'rootCA.pem')
      : path.join(os.homedir(), '.local', 'share', 'mkcert', 'rootCA.pem'),
].filter(Boolean);
function readBounded(file, maxBytes, encoding) {
  const descriptor = fs.openSync(file, 'r');
  try {
    const stat = fs.fstatSync(descriptor);
    if (!stat.isFile() || stat.size > maxBytes) throw new Error('invalid credential file');
    return fs.readFileSync(descriptor, encoding);
  } finally {
    fs.closeSync(descriptor);
  }
}

const localCa = localCaCandidates.reduce((loaded, candidate) => {
  if (loaded) return loaded;
  try {
    return readBounded(candidate, 16 * 1024 * 1024);
  } catch {
    return undefined;
  }
}, undefined) || (() => {
  try { return readBounded(localCaPath, 16 * 1024 * 1024); } catch { return undefined; }
})();
const host = process.env.TRINAXAI_PWA_HOST || '127.0.0.1';
const port = Number(process.env.TRINAXAI_PWA_PORT || process.env.PORT || 3334);
const proxyIdentityHeaders = [
  'x-trinaxai-proxy',
  'x-trinaxai-client-ip',
  'x-trinaxai-proxy-timestamp',
  'x-trinaxai-proxy-nonce',
  'x-trinaxai-proxy-signature',
];
const rateBuckets = new Map();
let proxySecretCache;

function env(name, fallback) {
  return process.env[name] || fallback;
}

function configuredPath(name, fallback) {
  const value = process.env[name];
  return value ? (path.isAbsolute(value) ? value : path.resolve(repoRoot, value)) : fallback;
}

function pairedDeviceGrants(token, scope) {
  if (!token) return false;
  try {
    const registryFile = configuredPath(
      'TRINAXAI_DEVICE_REGISTRY',
      path.join(repoRoot, 'storage', 'device_pairing.json'),
    );
    const secretFile = configuredPath(
      'TRINAXAI_DEVICE_SECRET_FILE',
      path.join(repoRoot, 'storage', '.device_secret'),
    );
    const registry = JSON.parse(readBounded(registryFile, 1024 * 1024, 'utf8'));
    const secret = readBounded(secretFile, 4096, 'ascii').trim();
    return deviceTokenHasScope(token, scope, registry, secret);
  } catch {
    return false;
  }
}

function proxySecret() {
  if (proxySecretCache !== undefined) return proxySecretCache;
  const configured = (process.env.TRINAXAI_PROXY_SECRET || '').trim();
  if (configured) return (proxySecretCache = configured);
  const secretFile = configuredPath(
    'TRINAXAI_PROXY_SECRET_FILE',
    path.join(repoRoot, 'storage', '.proxy_secret'),
  );
  try {
    proxySecretCache = readBounded(secretFile, 4096, 'utf8').trim();
  } catch (error) {
    if (error?.code !== 'ENOENT') return (proxySecretCache = '');
    const generated = randomBytes(32).toString('hex');
    try {
      fs.mkdirSync(path.dirname(secretFile), { recursive: true });
      fs.writeFileSync(secretFile, generated, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
      proxySecretCache = generated;
    } catch (writeError) {
      if (writeError?.code !== 'EEXIST') return (proxySecretCache = '');
      try {
        proxySecretCache = readBounded(secretFile, 4096, 'utf8').trim();
      } catch {
        proxySecretCache = '';
      }
    }
  }
  return proxySecretCache || '';
}

function sendJson(res, status, body) {
  res.writeHead(status, {
    ...PWA_SECURITY_HEADERS,
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
  });
  res.end(JSON.stringify(body));
}

function sendError(res, status, code) {
  sendJson(res, status, { ok: false, error: { code } });
}

function rateAllowed(peer) {
  const limit = Math.max(1, Number(process.env.TRINAXAI_OLLAMA_PROXY_RATE_LIMIT || 30) || 30);
  const now = Date.now();
  const previous = rateBuckets.get(peer) || { tokens: limit, updatedAt: now };
  const tokens = Math.min(limit, previous.tokens + ((now - previous.updatedAt) * limit) / 60_000);
  if (tokens < 1) {
    rateBuckets.set(peer, { tokens, updatedAt: now });
    return false;
  }
  if (!rateBuckets.has(peer) && rateBuckets.size >= 2000) {
    const oldest = [...rateBuckets.entries()].sort((a, b) => a[1].updatedAt - b[1].updatedAt)[0]?.[0];
    if (oldest) rateBuckets.delete(oldest);
  }
  rateBuckets.set(peer, { tokens: tokens - 1, updatedAt: now });
  return true;
}

function canonicalProxyPath(pathname) {
  try {
    return decodeURIComponent(pathname);
  } catch {
    return pathname;
  }
}

function signedIdentity(req, pathname) {
  const secret = proxySecret();
  const clientIp = normalizeAddress(req.socket.remoteAddress || 'unknown');
  if (!secret || net.isIP(clientIp) === 0) return {};
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = randomBytes(16).toString('hex');
  const payload = ['v1', clientIp, timestamp, nonce, req.method || 'GET', canonicalProxyPath(pathname)].join('\n');
  return {
    'x-trinaxai-proxy': 'v1',
    'x-trinaxai-client-ip': clientIp,
    'x-trinaxai-proxy-timestamp': timestamp,
    'x-trinaxai-proxy-nonce': nonce,
    'x-trinaxai-proxy-signature': createHmac('sha256', secret).update(payload, 'utf8').digest('hex'),
  };
}

function proxyTarget(name, fallback) {
  const target = new URL(env(name, fallback));
  if (!['http:', 'https:'].includes(target.protocol)) throw new Error(`${name} must use HTTP(S)`);
  return target;
}

async function proxyRequest(req, res, url, prefix) {
  const peer = normalizeAddress(req.socket.remoteAddress || 'unknown');
  const browserPath = url.pathname;
  const ollama = prefix === '/api/ollama';
  if (ollama) {
    if (!isAllowedOllamaProxyRequest(req.method || 'GET', browserPath)) {
      sendError(res, 404, 'proxy_operation_not_exposed');
      return;
    }
    const scope = requiredOllamaProxyScope(browserPath);
    const admin = String(req.headers['x-admin-token'] || '');
    const device = String(req.headers['x-trinaxai-device-token'] || '')
      || deviceTokenFromCookie(req.headers.cookie);
    const authorized = scope === 'system'
      ? isAuthorizedSystemProxyPeer(peer)
      : isAuthorizedScopedProxyPeer(
        peer,
        admin,
        process.env.TRINAXAI_ADMIN_TOKEN || '',
        device,
        pairedDeviceGrants(device, scope),
      );
    if (!authorized) {
      sendError(res, 403, 'proxy_scope_required');
      return;
    }
    if (!rateAllowed(peer)) {
      res.setHeader('Retry-After', '2');
      sendError(res, 429, 'proxy_rate_limited');
      return;
    }
  } else {
    if (!isLoopbackAddress(peer) && !proxySecret()) {
      sendError(res, 503, 'proxy_identity_unavailable');
      return;
    }
    const requiredScope = requiredRagProxyScope(browserPath, req.method || 'GET');
    const admin = String(req.headers['x-admin-token'] || '');
    const device = String(req.headers['x-trinaxai-device-token'] || '')
      || deviceTokenFromCookie(req.headers.cookie);
    const authorized = requiredScope === 'system'
      ? isAuthorizedSystemProxyPeer(peer)
      : isAuthorizedScopedProxyPeer(
        peer,
        admin,
        process.env.TRINAXAI_ADMIN_TOKEN || '',
        device,
        pairedDeviceGrants(device, requiredScope),
      );
    if (requiredScope && !authorized) {
      sendError(res, 403, 'proxy_scope_required');
      return;
    }
  }

  let target;
  try {
    target = ollama
      ? proxyTarget('TRINAXAI_OLLAMA_TARGET', 'http://127.0.0.1:11434')
      : proxyTarget('TRINAXAI_RAG_TARGET', env('VITE_TRINAXAI_RAG_TARGET', 'http://127.0.0.1:3333'));
  } catch (error) {
    console.error(`Invalid TrinaxAI proxy target: ${error.message}`);
    sendError(res, 503, 'proxy_invalid_configuration');
    return;
  }
  let release = () => {};
  // Model generation/pull/delete must be serialized, but a read-only health
  // probe must never wait behind an active stream. Otherwise the UI can report
  // Ollama as offline while Ollama is healthy and serving the current request.
  if (ollama && needsInferenceLock(browserPath)) {
    try {
      release = await acquireInferenceProcessLock(
        configuredPath('TRINAXAI_INFERENCE_LOCK_FILE', path.join(repoRoot, 'storage', '.inference.lock')),
        { timeoutMs: Math.max(1000, Number(process.env.TRINAXAI_INFERENCE_QUEUE_TIMEOUT || 600) * 1000) },
      );
    } catch {
      sendError(res, 503, 'proxy_queue_timeout');
      return;
    }
  }

  const upstreamPath = `${target.pathname.replace(/\/$/, '')}${browserPath.slice(prefix.length) || '/'}${url.search}`;
  const headers = { ...req.headers, host: target.host };
  headers['x-forwarded-proto'] = req.socket.encrypted ? 'https' : 'http';
  for (const header of proxyIdentityHeaders) delete headers[header];
  if (ollama) {
    delete headers['x-admin-token'];
    delete headers['x-trinaxai-device-token'];
    headers.origin = target.origin;
  } else {
    Object.assign(headers, signedIdentity(req, browserPath.slice(prefix.length) || '/'));
  }
  const client = target.protocol === 'https:' ? https : http;
  const localTls = target.protocol === 'https:' && isLoopbackAddress(target.hostname) && localCa;
  let released = false;
  const releaseOnce = () => {
    if (released) return;
    released = true;
    release();
  };
  let upstream;
  try {
    upstream = client.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port,
        method: req.method,
        path: upstreamPath,
        headers,
        ...(localTls ? { ca: localCa } : {}),
      },
      (upstreamResponse) => {
        res.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
        upstreamResponse.pipe(res);
        upstreamResponse.once('end', releaseOnce);
        upstreamResponse.once('close', releaseOnce);
      },
    );
  } catch (error) {
    console.error('TrinaxAI proxy setup failure.');
    releaseOnce();
    sendError(res, 502, 'proxy_unavailable');
    return;
  }
  upstream.on('error', (error) => {
    console.error('TrinaxAI proxy failure.');
    releaseOnce();
    if (!res.headersSent) sendError(res, 502, 'proxy_unavailable');
    else res.destroy();
  });
  req.once('aborted', () => {
    upstream.destroy();
    releaseOnce();
  });
  // A completed request emits `close` after the response is writable. When a
  // browser cancels a streaming response, however, only the response closes;
  // aborting the upstream here prevents an orphaned Ollama stream from holding
  // the process lock indefinitely.
  res.once('close', () => {
    if (res.writableEnded) return;
    upstream.destroy();
    releaseOnce();
  });
  req.pipe(upstream);
}

function localPython() {
  const candidates = [
    process.env.TRINAXAI_PYTHON,
    path.join(repoRoot, '.venv', 'bin', 'python'),
    path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),
  ].filter(Boolean);
  return candidates.find((candidate) => fs.existsSync(candidate))
    || (process.platform === 'win32' ? 'python' : 'python3');
}

function systemAuthorized(req) {
  const peer = normalizeAddress(req.socket.remoteAddress || 'unknown');
  const origin = String(req.headers.origin || '');
  const trustedOrigin = !origin || (() => {
    try {
      const parsed = new URL(origin);
      return parsed.port === String(port) && isLoopbackAddress(parsed.hostname);
    } catch {
      return false;
    }
  })();
  return trustedOrigin && isAuthorizedSystemProxyPeer(peer);
}

function lanAddresses() {
  const addresses = [];
  for (const [name, entries] of Object.entries(os.networkInterfaces())) {
    if (/^(docker|br-|veth|virbr)/i.test(name)) continue;
    for (const entry of entries || []) {
      const address = normalizeAddress(entry.address || '');
      const linkLocal = /^(fe8|fe9|fea|feb)/i.test(address);
      if (!entry.internal && !linkLocal && isPrivateLanAddress(address) && !addresses.includes(address)) addresses.push(address);
    }
  }
  return addresses.sort((left, right) => Number(left.includes(':')) - Number(right.includes(':')) || left.localeCompare(right));
}

function hasExistingInstallation() {
  try {
    const raw = JSON.parse(readBounded(path.join(repoRoot, 'storage', 'app_state.json'), 6 * 1024 * 1024, 'utf8'));
    const values = raw?.schema_version === 2 ? raw.values : raw;
    return values?.['tc-onboarding-complete'] === 'true';
  } catch {
    return false;
  }
}

// The running service keeps the environment it was started with, so the file on
// disk is the only current source for origins refreshed after a network change.
function configuredCorsOrigins() {
  try {
    const lines = readBounded(path.join(repoRoot, '.env'), 1024 * 1024, 'utf8').split('\n');
    for (let index = lines.length - 1; index >= 0; index -= 1) {
      if (lines[index].startsWith('TRINAXAI_CORS_ORIGINS=')) return lines[index].split('=', 2)[1].trim();
    }
  } catch { /* Without a readable .env the process environment is the best source. */ }
  return String(process.env.TRINAXAI_CORS_ORIGINS || '');
}

function networkStatus() {
  const hostname = os.hostname().split('.', 1)[0] || 'trinaxai';
  const stableHost = `${hostname}.local`;
  const addresses = lanAddresses();
  const renderUrl = (address) => `https://${address.includes(':') ? `[${address}]` : address}:${port}`;
  const urls = [...addresses.map(renderUrl), renderUrl(stableHost)];
  const configuredOrigins = configuredCorsOrigins();
  const configurationCurrent = urls.every((url) => configuredOrigins.includes(url));
  let certificateCurrent = null;
  try {
    const certificate = new X509Certificate(readBounded(localCaPath, 1024 * 1024));
    const subjectAltName = certificate.subjectAltName || '';
    certificateCurrent = subjectAltName.includes(`DNS:${stableHost}`)
      && addresses.every((address) => subjectAltName.includes(`IP Address:${address}`));
  } catch { /* PFX-only Windows installs are checked by the refresh command. */ }
  return {
    online: true,
    existingInstallation: hasExistingInstallation(),
    hostname,
    addresses,
    urls,
    recommendedUrl: urls[0],
    configurationCurrent,
    certificateCurrent,
    needsRefresh: !configurationCurrent || certificateCurrent === false,
    refreshCommand: 'trinaxai network refresh',
  };
}

function networkInfo(req, res) {
  if (req.method !== 'GET') {
    sendError(res, 405, 'method_not_allowed');
    return;
  }
  sendJson(res, 200, {
    ...networkStatus(),
    capabilities: { manageSystem: isAuthorizedSystemProxyPeer(req.socket.remoteAddress || 'unknown') },
  });
}

function systemControl(req, res, pathname) {
  if (req.method !== 'POST') {
    sendError(res, 405, 'method_not_allowed');
    return;
  }
  if (!systemAuthorized(req)) {
    sendError(res, 403, 'system_scope_required');
    return;
  }
  const action = pathname.slice('/api/system/'.length);
  if (action === 'network-refresh') {
    const args = [
      '-m', 'trinaxai_cli', '--install-root', repoRoot,
      'network', 'refresh', '--yes', '--no-restart',
    ];
    execFile(localPython(), args, { cwd: repoRoot, windowsHide: true }, (error) => {
      if (error) {
        console.error(`TrinaxAI network refresh failed: ${error.message}`);
        sendError(res, 500, 'network_refresh_failed');
        return;
      }
      sendJson(res, 200, { ok: true, ...networkStatus(), restartRequired: true });
      setTimeout(() => {
        const child = spawn(
          localPython(),
          [path.join(repoRoot, 'service_manager.py'), 'reload-network', '--base-dir', repoRoot],
          { cwd: repoRoot, detached: true, stdio: 'ignore', windowsHide: true },
        );
        child.unref();
      }, 400);
    });
    return;
  }
  const managerAction = action === 'startup' ? 'start-ai' : action === 'shutdown' ? 'stop-ai' : 'stop-all';
  if (!['startup', 'shutdown', 'stop-all'].includes(action)) {
    sendError(res, 404, 'unknown_system_action');
    return;
  }
  const args = [path.join(repoRoot, 'service_manager.py'), managerAction, '--base-dir', repoRoot];
  if (action !== 'startup') {
    sendJson(res, 200, { ok: true, output: 'System action initiated.' });
    setTimeout(() => {
      const child = spawn(localPython(), args, { cwd: repoRoot, detached: true, stdio: 'ignore', windowsHide: true });
      child.unref();
    }, action === 'stop-all' ? 250 : 50);
    return;
  }
  execFile(localPython(), args, { cwd: repoRoot, windowsHide: true }, (error) => {
    if (error) {
      console.error(`TrinaxAI startup failed: ${error.message}`);
      sendError(res, 500, 'system_start_failed');
    } else {
      sendJson(res, 200, { ok: true, output: 'AI services started.' });
    }
  });
}

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function staticFile(url) {
  let pathname;
  try {
    pathname = decodeURIComponent(url.pathname);
  } catch {
    return null;
  }
  const candidate = path.resolve(distDir, `.${pathname}`);
  if (candidate !== distDir && !candidate.startsWith(`${distDir}${path.sep}`)) return null;
  try {
    if (fs.statSync(candidate).isFile()) return candidate;
  } catch {
    // Missing files fall through to the SPA fallback below.
  }
  if (path.extname(pathname)) return null;
  return path.join(distDir, 'index.html');
}

function serveStatic(req, res, url) {
  const file = staticFile(url);
  if (!file || !fs.existsSync(file)) {
    sendError(res, 404, 'frontend_build_missing');
    return;
  }
  const extension = path.extname(file).toLowerCase();
  const immutable = url.pathname.startsWith('/assets/');
  res.writeHead(200, {
    ...PWA_SECURITY_HEADERS,
    'Content-Type': contentTypes[extension] || 'application/octet-stream',
    'Cache-Control': immutable ? 'public, max-age=31536000, immutable' : 'no-cache',
  });
  if (req.method === 'HEAD') res.end();
  else {
    const stream = fs.createReadStream(file);
    stream.on('error', () => res.destroy());
    stream.pipe(res);
  }
}

function requestHandler(req, res) {
  let url;
  try {
    url = new URL(req.url || '/', 'http://localhost');
  } catch {
    sendError(res, 400, 'invalid_request_url');
    return;
  }
  if (url.pathname === '/api/rag' || url.pathname.startsWith('/api/rag/')) {
    void proxyRequest(req, res, url, '/api/rag');
  } else if (url.pathname === '/api/ollama' || url.pathname.startsWith('/api/ollama/')) {
    void proxyRequest(req, res, url, '/api/ollama');
  } else if (url.pathname.startsWith('/api/system/')) {
    systemControl(req, res, url.pathname);
  } else if (url.pathname === '/api/network') {
    networkInfo(req, res);
  } else if (url.pathname.startsWith('/api/')) {
    sendError(res, 404, 'route_not_found');
  } else if (req.method === 'GET' || req.method === 'HEAD') {
    serveStatic(req, res, url);
  } else {
    sendError(res, 404, 'route_not_found');
  }
}

if (!fs.existsSync(distDir)) {
  console.error('TrinaxAI frontend build is missing. Run npm run build.');
  process.exitCode = 1;
} else if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error('TRINAXAI_PWA_PORT must be a valid TCP port.');
  process.exitCode = 1;
} else {
  const pfx = path.join(certDir, 'trinaxai-local.pfx');
  const key = path.join(certDir, 'localhost-key.pem');
  const cert = path.join(certDir, 'localhost.pem');
  const tlsEnabled = process.env.CI !== 'true' && (fs.existsSync(pfx) || (fs.existsSync(key) && fs.existsSync(cert)));
  const insecureHttpAllowed = process.env.TRINAXAI_ALLOW_INSECURE_HTTP === '1';
  if (!tlsEnabled && !isLoopbackAddress(host) && !insecureHttpAllowed) {
    console.error(
      'Refusing insecure HTTP on a non-loopback PWA host. Generate local TLS certificates or set '
        + 'TRINAXAI_ALLOW_INSECURE_HTTP=1 only for an explicitly trusted test network.',
    );
    process.exitCode = 1;
  } else {
    const tlsOptions = () => (fs.existsSync(pfx)
      ? { pfx: fs.readFileSync(pfx), passphrase: process.env.TRINAXAI_CERT_PASSPHRASE || 'trinaxai-local' }
      : { key: fs.readFileSync(key), cert: fs.readFileSync(cert) });
    const server = tlsEnabled ? https.createServer(tlsOptions(), requestHandler) : http.createServer(requestHandler);
    if (tlsEnabled) {
      // A network refresh renews the certificate in place; adopting it here keeps
      // the new LAN address trusted without requiring a privileged restart.
      let reloadTimer;
      fs.watch(certDir, () => {
        clearTimeout(reloadTimer);
        reloadTimer = setTimeout(() => {
          try {
            server.setSecureContext(tlsOptions());
            console.log('TrinaxAI PWA reloaded the local HTTPS certificate.');
          } catch (error) {
            console.error(`TrinaxAI PWA kept the previous certificate: ${error.message}`);
          }
        }, 500).unref();
      }).unref();
    }
    server.listen(port, host, () => {
      console.log(`TrinaxAI PWA listening on ${tlsEnabled ? 'https' : 'http'}://${host}:${port}`);
    });
  }
}
