import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const appDir = fileURLToPath(new URL('.', import.meta.url));

function ensureFrontendFixture() {
  const distDir = path.join(appDir, 'dist');
  fs.mkdirSync(distDir, { recursive: true });
  const indexPath = path.join(distDir, 'index.html');
  try {
    const descriptor = fs.openSync(indexPath, 'wx');
    try {
      fs.writeFileSync(descriptor, '<!doctype html><title>test</title>\n');
    } finally {
      fs.closeSync(descriptor);
    }
  } catch (error) {
    if (error?.code !== 'EEXIST') throw error;
  }
}

function privateLanAddress() {
  for (const entries of Object.values(os.networkInterfaces())) {
    for (const entry of entries || []) {
      if (entry.family === 'IPv4' && !entry.internal && /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(entry.address)) {
        return entry.address;
      }
    }
  }
  return '';
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
  });
}

async function unusedPort() {
  const server = http.createServer();
  const port = await listen(server);
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function waitFor(predicate, timeoutMs = 3000) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error('timed out waiting for test state');
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}

test('refuses insecure HTTP on a non-loopback host by default', async () => {
  ensureFrontendFixture();
  const gatewayPort = await unusedPort();
  const gateway = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: {
      ...process.env,
      CI: 'true',
      TRINAXAI_PWA_HOST: '0.0.0.0',
      TRINAXAI_PWA_PORT: String(gatewayPort),
      TRINAXAI_ALLOW_INSECURE_HTTP: '0',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stderr = '';
  gateway.stderr.on('data', (chunk) => { stderr += String(chunk); });
  const [code] = await once(gateway, 'exit');
  assert.notEqual(code, 0);
  assert.match(stderr, /refusing insecure HTTP/i);
});

test('network status reads CORS origins from disk instead of the stale service environment', async () => {
  ensureFrontendFixture();
  const gatewayPort = await unusedPort();
  const gateway = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: {
      ...process.env,
      CI: 'true',
      TRINAXAI_PWA_HOST: '127.0.0.1',
      TRINAXAI_PWA_PORT: String(gatewayPort),
      // A refresh rewrites .env while the service keeps this outdated value.
      TRINAXAI_CORS_ORIGINS: 'https://stale.invalid:3334',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('gateway startup timed out')), 5000);
      gateway.once('exit', (code) => reject(new Error(`gateway exited with ${code}`)));
      gateway.stdout.on('data', (chunk) => {
        if (!String(chunk).includes('listening')) return;
        clearTimeout(timeout);
        resolve();
      });
    });

    const status = await (await fetch(`http://127.0.0.1:${gatewayPort}/api/network`)).json();
    let onDisk = '';
    try {
      const lines = fs.readFileSync(path.join(appDir, '..', '.env'), 'utf8').split('\n');
      onDisk = lines.filter((line) => line.startsWith('TRINAXAI_CORS_ORIGINS=')).pop()?.split('=', 2)[1].trim() || '';
    } catch { /* Without a .env the status falls back to the process environment. */ }
    assert.equal(
      status.configurationCurrent,
      status.urls.every((url) => (onDisk || 'https://stale.invalid:3334').includes(url)),
    );
  } finally {
    gateway.kill();
  }
});

test('production gateway preserves credentials, replaces proxy identity, and rejects missing assets', async () => {
  ensureFrontendFixture();
  let received;
  const backend = http.createServer((req, res) => {
    received = { path: req.url, headers: req.headers };
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': 'trinaxai-device-token=backend-cookie; Path=/api/rag; HttpOnly; SameSite=Strict',
    });
    res.end('{"ok":true}');
  });
  const backendPort = await listen(backend);
  const gatewayPort = await unusedPort();
  const gateway = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: {
      ...process.env,
      CI: 'true',
      TRINAXAI_PWA_HOST: '127.0.0.1',
      TRINAXAI_PWA_PORT: String(gatewayPort),
      TRINAXAI_RAG_TARGET: `http://127.0.0.1:${backendPort}`,
      TRINAXAI_PROXY_SECRET: 'test-only-proxy-secret',
      TRINAXAI_ADMIN_TOKEN: 'test-admin-token',
      TRINAXAI_PWA_MAX_BODY_BYTES: '4',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('gateway startup timed out')), 5000);
      gateway.once('exit', (code) => reject(new Error(`gateway exited with ${code}`)));
      gateway.stdout.on('data', (chunk) => {
        if (!String(chunk).includes('listening')) return;
        clearTimeout(timeout);
        resolve();
      });
    });

    const response = await fetch(`http://127.0.0.1:${gatewayPort}/api/rag/private?value=1`, {
      headers: {
        'X-Admin-Token': 'test-admin-token',
        'X-TrinaxAI-Device-Token': 'device-credential',
        Cookie: 'trinaxai-device-token=cookie-credential',
        'X-TrinaxAI-Proxy': 'browser-spoof',
      },
    });
    assert.equal(response.status, 200);
    assert.equal(received.path, '/private?value=1');
    assert.equal(received.headers['x-trinaxai-device-token'], 'device-credential');
    assert.equal(received.headers.cookie, 'trinaxai-device-token=cookie-credential');
    assert.equal(received.headers['x-trinaxai-proxy'], 'v1');
    assert.notEqual(received.headers['x-trinaxai-proxy-signature'], undefined);
    assert.match(response.headers.get('set-cookie') || '', /HttpOnly/);
    assert.match(response.headers.get('set-cookie') || '', /Path=\/api\/rag/);

    const encodedPath = await fetch(`http://127.0.0.1:${gatewayPort}/api/rag/private%20file?value=1`, {
      headers: { 'X-Admin-Token': 'test-admin-token', 'X-TrinaxAI-Device-Token': 'device-credential' },
    });
    assert.equal(encodedPath.status, 200);
    const signedPath = '/private file';
    const payload = [
      'v1',
      '127.0.0.1',
      received.headers['x-trinaxai-proxy-timestamp'],
      received.headers['x-trinaxai-proxy-nonce'],
      'GET',
      signedPath,
    ].join('\n');
    const expectedSignature = createHmac('sha256', 'test-only-proxy-secret').update(payload, 'utf8').digest('hex');
    assert.equal(received.path, '/private%20file?value=1');
    assert.equal(received.headers['x-trinaxai-proxy-signature'], expectedSignature);

    const oversized = await fetch(`http://127.0.0.1:${gatewayPort}/api/rag/private`, {
      method: 'POST',
      headers: { 'X-Admin-Token': 'test-admin-token', 'Content-Type': 'text/plain' },
      body: '12345',
    });
    assert.equal(oversized.status, 413);
    assert.deepEqual((await oversized.json()).error, { code: 'proxy_body_too_large' });

    const missing = await fetch(`http://127.0.0.1:${gatewayPort}/assets/missing.js`);
    assert.equal(missing.status, 404);

    const network = await fetch(`http://127.0.0.1:${gatewayPort}/api/network`);
    assert.equal(network.status, 200);
    const networkBody = await network.json();
    assert.equal(networkBody.online, true);
    assert.equal(networkBody.capabilities.manageSystem, true);
    assert.equal(typeof networkBody.existingInstallation, 'boolean');
    assert.equal(networkBody.refreshCommand, 'trinaxai network refresh');
    assert.match(networkBody.recommendedUrl, /^https:\/\/(?:\d{1,3}\.){3}\d{1,3}:/);

    const forbiddenRefresh = await fetch(`http://127.0.0.1:${gatewayPort}/api/system/network-refresh`, {
      method: 'POST',
      headers: { Origin: 'https://example.com' },
    });
    assert.equal(forbiddenRefresh.status, 403);
  } finally {
    gateway.kill();
    await new Promise((resolve) => backend.close(resolve));
  }
});

test('production gateway returns a timeout when the upstream stalls', async () => {
  ensureFrontendFixture();
  const backend = http.createServer(() => {});
  const backendPort = await listen(backend);
  const gatewayPort = await unusedPort();
  const gateway = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: {
      ...process.env,
      CI: 'true',
      TRINAXAI_PWA_HOST: '127.0.0.1',
      TRINAXAI_PWA_PORT: String(gatewayPort),
      TRINAXAI_RAG_TARGET: `http://127.0.0.1:${backendPort}`,
      TRINAXAI_ADMIN_TOKEN: 'test-admin-token',
      TRINAXAI_PWA_PROXY_TIMEOUT_MS: '100',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('gateway startup timed out')), 5000);
      gateway.once('exit', (code) => reject(new Error(`gateway exited with ${code}`)));
      gateway.stdout.on('data', (chunk) => {
        if (!String(chunk).includes('listening')) return;
        clearTimeout(timeout);
        resolve();
      });
    });
    const controller = new AbortController();
    const abortTimer = setTimeout(() => controller.abort(), 2000);
    const response = await fetch(`http://127.0.0.1:${gatewayPort}/api/rag/private`, {
      headers: { 'X-Admin-Token': 'test-admin-token' },
      signal: controller.signal,
    });
    clearTimeout(abortTimer);
    assert.equal(response.status, 504);
    assert.deepEqual((await response.json()).error, { code: 'proxy_timeout' });
  } finally {
    gateway.kill();
    await new Promise((resolve) => backend.close(resolve));
  }
});

test('production gateway rejects LAN host administration even with legacy credentials', async (t) => {
  const lanAddress = privateLanAddress();
  if (!lanAddress) return t.skip('no private LAN interface is available');
  ensureFrontendFixture();
  const gatewayPort = await unusedPort();
  const credentialsRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'trinaxai-legacy-device-'));
  const secret = 'ab'.repeat(32);
  const id = '0123456789abcdef01234567';
  const token = `txd_${id}_${'z'.repeat(43)}`;
  const tokenHash = createHmac('sha256', Buffer.from(secret, 'hex'))
    .update(`device-token\0${token}`)
    .digest('hex');
  const registryPath = path.join(credentialsRoot, 'registry.json');
  const secretPath = path.join(credentialsRoot, 'secret');
  fs.writeFileSync(registryPath, JSON.stringify({
    schema_version: 1,
    pairing_codes: {},
    devices: {
      [id]: { id, token_hash: tokenHash, scopes: ['system'], expires_at: null, revoked_at: null },
    },
  }));
  fs.writeFileSync(secretPath, secret);
  const gateway = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: {
      ...process.env,
      CI: 'true',
      TRINAXAI_PWA_HOST: '0.0.0.0',
      TRINAXAI_PWA_PORT: String(gatewayPort),
      TRINAXAI_ALLOW_INSECURE_HTTP: '1',
      TRINAXAI_ADMIN_TOKEN: 'remote-admin',
      TRINAXAI_DEVICE_REGISTRY: registryPath,
      TRINAXAI_DEVICE_SECRET_FILE: secretPath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('gateway startup timed out')), 5000);
      gateway.once('exit', (code) => reject(new Error(`gateway exited with ${code}`)));
      gateway.stdout.on('data', (chunk) => {
        if (!String(chunk).includes('listening')) return;
        clearTimeout(timeout);
        resolve();
      });
    });
    const base = `http://${lanAddress}:${gatewayPort}`;
    for (const headers of [
      { 'X-Admin-Token': 'remote-admin', Origin: `http://localhost:${gatewayPort}` },
      { 'X-TrinaxAI-Device-Token': token, Host: `localhost:${gatewayPort}` },
      { 'X-Forwarded-For': '127.0.0.1' },
    ]) {
      const system = await fetch(`${base}/api/system/stop-all`, { method: 'POST', headers });
      assert.equal(system.status, 403);
      const pull = await fetch(`${base}/api/ollama/api/pull`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: '{"name":"example"}',
      });
      assert.equal(pull.status, 403);
      const remove = await fetch(`${base}/api/ollama/api/delete`, {
        method: 'DELETE',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: '{"name":"example"}',
      });
      assert.equal(remove.status, 403);
    }
    const chat = await fetch(`${base}/api/ollama/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{"model":"example","messages":[]}',
    });
    assert.equal(chat.status, 403);
    const network = await (await fetch(`${base}/api/network`)).json();
    assert.equal(network.capabilities.manageSystem, false);
    assert.equal('hostname' in network, false);
    assert.equal('addresses' in network, false);
    assert.equal('recommendedUrl' in network, false);
  } finally {
    gateway.kill();
    fs.rmSync(credentialsRoot, { recursive: true, force: true });
  }
});

test('production gateway releases abandoned inference streams and keeps tags responsive', async () => {
  ensureFrontendFixture();
  let chatRequests = 0;
  let firstChatClosed = false;
  const backend = http.createServer((req, res) => {
    if (req.url === '/api/tags') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{"models":[]}');
      return;
    }
    if (req.url !== '/api/chat') {
      res.writeHead(404);
      res.end();
      return;
    }
    chatRequests += 1;
    if (chatRequests === 1) {
      req.once('close', () => { firstChatClosed = true; });
      res.writeHead(200, { 'Content-Type': 'application/x-ndjson' });
      res.write('{"message":{"content":"partial"}}\n');
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/x-ndjson' });
    res.end('{"message":{"content":"complete"}}\n');
  });
  const backendPort = await listen(backend);
  const gatewayPort = await unusedPort();
  const lockRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'trinaxai-gateway-'));
  const lockPath = path.join(lockRoot, 'inference.lock');
  const gateway = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: {
      ...process.env,
      CI: 'true',
      TRINAXAI_PWA_HOST: '127.0.0.1',
      TRINAXAI_PWA_PORT: String(gatewayPort),
      TRINAXAI_OLLAMA_TARGET: `http://127.0.0.1:${backendPort}`,
      TRINAXAI_INFERENCE_LOCK_FILE: lockPath,
      TRINAXAI_INFERENCE_QUEUE_TIMEOUT: '2',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('gateway startup timed out')), 5000);
      gateway.once('exit', (code) => reject(new Error(`gateway exited with ${code}`)));
      gateway.stdout.on('data', (chunk) => {
        if (!String(chunk).includes('listening')) return;
        clearTimeout(timeout);
        resolve();
      });
    });

    const controller = new AbortController();
    const firstResponse = await fetch(`http://127.0.0.1:${gatewayPort}/api/ollama/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{"model":"test","messages":[],"stream":true}',
      signal: controller.signal,
    });
    assert.equal(firstResponse.status, 200);
    await waitFor(() => chatRequests === 1);
    assert.equal((await fetch(`http://127.0.0.1:${gatewayPort}/api/ollama/api/tags`)).status, 200);

    controller.abort();
    await firstResponse.body?.cancel().catch(() => undefined);
    await waitFor(() => firstChatClosed);
    await waitFor(() => !fs.existsSync(lockPath));

    const secondResponse = await fetch(`http://127.0.0.1:${gatewayPort}/api/ollama/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{"model":"test","messages":[],"stream":true}',
    });
    assert.equal(secondResponse.status, 200);
    assert.match(await secondResponse.text(), /complete/);
  } finally {
    gateway.kill();
    await new Promise((resolve) => backend.close(resolve));
    fs.rmSync(lockRoot, { recursive: true, force: true });
  }
});
