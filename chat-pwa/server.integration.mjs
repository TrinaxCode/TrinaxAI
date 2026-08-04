import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { spawn } from 'node:child_process';
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
    res.writeHead(200, { 'Content-Type': 'application/json' });
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
        'X-TrinaxAI-Device-Token': 'device-credential',
        'X-TrinaxAI-Proxy': 'browser-spoof',
      },
    });
    assert.equal(response.status, 200);
    assert.equal(received.path, '/private?value=1');
    assert.equal(received.headers['x-trinaxai-device-token'], 'device-credential');
    assert.equal(received.headers['x-trinaxai-proxy'], 'v1');
    assert.notEqual(received.headers['x-trinaxai-proxy-signature'], undefined);

    const encodedPath = await fetch(`http://127.0.0.1:${gatewayPort}/api/rag/private%20file?value=1`, {
      headers: { 'X-TrinaxAI-Device-Token': 'device-credential' },
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

    const missing = await fetch(`http://127.0.0.1:${gatewayPort}/assets/missing.js`);
    assert.equal(missing.status, 404);

    const network = await fetch(`http://127.0.0.1:${gatewayPort}/api/network`);
    assert.equal(network.status, 200);
    const networkBody = await network.json();
    assert.equal(networkBody.online, true);
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
