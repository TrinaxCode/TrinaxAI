import { describe, expect, it } from 'vitest';
import { createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  isAllowedOllamaProxyRequest,
  deviceTokenHasScope,
  deviceTokenFromCookie,
  isAuthorizedOllamaProxyPeer,
  isElevatedDeviceScope,
  isAuthorizedScopedProxyPeer,
  isAuthorizedSystemProxyPeer,
  isLoopbackAddress,
  isPrivateLanAddress,
  isTrustedHostHeader,
  needsInferenceLock,
  requiredOllamaProxyScope,
  requiredRagProxyScope,
} from './vite-security';

describe('Vite security boundary', () => {
  it('keeps the offline shell compatible with the production CSP', () => {
    const offline = readFileSync(resolve(process.cwd(), 'public/offline.html'), 'utf8');
    expect(offline).not.toMatch(/on(click|load)\s*=/i);
    expect(offline).not.toMatch(/<script>(?!\s*<\/script>)[\s\S]*<\/script>/i);
    expect(offline).toContain('<script src="/offline.js" defer></script>');
  });

  it('exposes only the Ollama operations required by the PWA', () => {
    expect(isAllowedOllamaProxyRequest('GET', '/api/ollama/api/tags')).toBe(true);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/chat')).toBe(true);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/generate')).toBe(true);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/pull')).toBe(true);

    expect(isAllowedOllamaProxyRequest('DELETE', '/api/ollama/api/delete')).toBe(true);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/delete')).toBe(false);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/create')).toBe(false);
    expect(isAllowedOllamaProxyRequest('GET', '/api/ollama/api/ps')).toBe(false);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/tags')).toBe(false);
    expect(isAllowedOllamaProxyRequest('POST', '/api/ollama/api/chat/../delete')).toBe(false);
  });

  it('requires system scope for every model administration operation', () => {
    expect(requiredOllamaProxyScope('/api/ollama/api/tags')).toBe('chat');
    expect(requiredOllamaProxyScope('/api/ollama/api/chat')).toBe('chat');
    expect(requiredOllamaProxyScope('/api/ollama/api/generate')).toBe('chat');
    expect(requiredOllamaProxyScope('/api/ollama/api/pull')).toBe('system');
    expect(requiredOllamaProxyScope('/api/ollama/api/delete')).toBe('system');
  });

  it('keeps read-only model discovery responsive during inference', () => {
    expect(needsInferenceLock('/api/ollama/api/tags')).toBe(false);
    expect(needsInferenceLock('/api/ollama/api/chat')).toBe(true);
  });

  it('requires paired-device scopes for protected RAG areas', () => {
    expect(requiredRagProxyScope('/api/rag/health')).toBeNull();
    expect(requiredRagProxyScope('/api/rag/v1/pairing/claim')).toBeNull();
    expect(requiredRagProxyScope('/api/rag/v1/pairing/me', 'DELETE')).toBeNull();
    expect(requiredRagProxyScope('/api/rag/v1/pairing/new-device', 'POST')).toBeNull();
    expect(requiredRagProxyScope('/api/rag/v1/pairing/start', 'POST')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/v1/pairing/devices', 'GET')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/v1/pairing/devices/id', 'DELETE')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/v1/pairing/devices/id', 'PATCH')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/v1/agent')).toBe('agent');
    expect(requiredRagProxyScope('/api/rag/v1/agent/approve', 'POST')).toBe('agent');
    expect(requiredRagProxyScope('/api/rag/system/index-upload')).toBe('index');
    expect(requiredRagProxyScope('/api/rag/v1/watch/start', 'POST')).toBe('index');
    expect(requiredRagProxyScope('/api/rag/system/shutdown', 'POST')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/collections', 'GET')).toBe('read_private');
    expect(requiredRagProxyScope('/api/rag/collections', 'POST')).toBe('index');
    expect(requiredRagProxyScope('/api/rag/v1/sources')).toBe('read_private');
    expect(requiredRagProxyScope('/api/rag/v1/sources/file.txt/chunks', 'DELETE')).toBe('index');
    expect(requiredRagProxyScope('/api/rag/attachments/id/open', 'POST')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/attachments/id', 'DELETE')).toBe('modify');
    expect(requiredRagProxyScope('/api/rag/v1/memory', 'GET')).toBe('read_private');
    expect(requiredRagProxyScope('/api/rag/v1/memory', 'POST')).toBe('modify');
    expect(requiredRagProxyScope('/api/rag/app-state', 'DELETE')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/v1/settings/web-search', 'GET')).toBe('modify');
    expect(requiredRagProxyScope('/api/rag/v1/settings/web-search', 'PUT')).toBe('modify');
    expect(requiredRagProxyScope('/api/rag/v1/settings', 'PUT')).toBe('system');
    expect(requiredRagProxyScope('/api/rag/v1/chat/completions')).toBe('chat');
  });

  it('extracts only the exact HttpOnly device cookie', () => {
    expect(deviceTokenFromCookie('other=value; trinaxai-device-token=cookie-secret; theme=dark')).toBe('cookie-secret');
    expect(deviceTokenFromCookie('trinaxai-device-token=cookie%2Dsecret')).toBe('cookie-secret');
    expect(deviceTokenFromCookie('trinaxai-device-token-legacy=wrong')).toBe('');
    expect(deviceTokenFromCookie('trinaxai-device-token=')).toBe('');
  });

  it('keeps localhost usable but requires the configured token remotely', () => {
    expect(isAuthorizedOllamaProxyPeer('127.0.0.1', '', 'configured')).toBe(true);
    expect(isAuthorizedOllamaProxyPeer('::1', '', 'configured')).toBe(true);
    expect(isAuthorizedOllamaProxyPeer('127.0.0.1', 'wrong', 'configured')).toBe(false);
    expect(isAuthorizedOllamaProxyPeer('192.168.1.20', 'configured', 'configured')).toBe(true);
    expect(isAuthorizedOllamaProxyPeer('192.168.1.20', '', 'configured')).toBe(false);
    expect(isAuthorizedOllamaProxyPeer('192.168.1.20', 'wrong', 'configured')).toBe(false);
    expect(isAuthorizedOllamaProxyPeer('192.168.1.20', '', '')).toBe(false);
  });

  it('recognizes loopback and actual LAN ranges without treating public IPs as LAN', () => {
    expect(isLoopbackAddress('::ffff:127.0.0.1')).toBe(true);
    expect(isPrivateLanAddress('10.1.2.3')).toBe(true);
    expect(isPrivateLanAddress('172.31.4.5')).toBe(true);
    expect(isPrivateLanAddress('192.168.0.8')).toBe(true);
    expect(isPrivateLanAddress('fd00::1')).toBe(true);
    expect(isPrivateLanAddress('8.8.8.8')).toBe(false);
    expect(isPrivateLanAddress('2001:4860:4860::8888')).toBe(false);
  });

  it('rejects DNS-rebinding Host headers but keeps local and LAN names', () => {
    for (const host of [undefined, '', 'localhost:3334', 'LOCALHOST.', '127.0.0.1:3334', '[::1]:3334', '::1', 'app.localhost', 'laptop.local:3334', '192.168.1.5:3334']) {
      expect(isTrustedHostHeader(host)).toBe(true);
    }
    for (const host of ['evil.example', 'evil.example.:3334', '[::1', '[]:3334']) {
      expect(isTrustedHostHeader(host)).toBe(false);
    }
    expect(isTrustedHostHeader('AI.home.arpa:3334', ' ai.home.arpa. , ')).toBe(true);
    expect(isTrustedHostHeader('evil.example', 'ai.home.arpa')).toBe(false);
    expect(isTrustedHostHeader('evil.example', '*')).toBe(true);
  });

  it('keeps every system-control operation on the real loopback peer', () => {
    expect(isAuthorizedSystemProxyPeer('192.168.1.20')).toBe(false);
    expect(isAuthorizedSystemProxyPeer('8.8.8.8')).toBe(false);
    expect(isAuthorizedSystemProxyPeer('127.0.0.1')).toBe(true);
    expect(isAuthorizedSystemProxyPeer('::1')).toBe(true);
  });

  it('validates scoped paired-device tokens and rejects revocation or scope escalation', () => {
    const secret = 'ab'.repeat(32);
    const id = '0123456789abcdef01234567';
    const token = `txd_${id}_${'z'.repeat(43)}`;
    const tokenHash = createHmac('sha256', Buffer.from(secret, 'hex'))
      .update(`device-token\0${token}`)
      .digest('hex');
    const registry = {
      schema_version: 1,
      devices: {
        [id]: {
          id,
          token_hash: tokenHash,
          scopes: ['chat', 'read_private', 'system'],
          expires_at: null,
          revoked_at: null,
        },
      },
    };

    expect(deviceTokenHasScope(token, 'chat', registry, secret)).toBe(true);
    expect(isAuthorizedScopedProxyPeer('192.168.1.20', '', 'admin', token, true)).toBe(true);
    expect(isAuthorizedScopedProxyPeer('192.168.1.20', '', 'admin', token, false)).toBe(false);
    // An explicitly invalid admin credential cannot be rescued by also adding
    // a valid device token, matching FastAPI's ambiguity-resistant behavior.
    expect(isAuthorizedScopedProxyPeer('192.168.1.20', 'wrong', 'admin', token, true)).toBe(false);
    expect(deviceTokenHasScope(token, 'system', registry, secret)).toBe(false);
    expect(deviceTokenHasScope(token, 'agent', registry, secret)).toBe(false);
    expect(deviceTokenHasScope(token, 'index', registry, secret)).toBe(false);
    expect(deviceTokenHasScope(`${token}bad`, 'chat', registry, secret)).toBe(false);
    registry.devices[id].revoked_at = 123;
    expect(deviceTokenHasScope(token, 'chat', registry, secret)).toBe(false);
  });

  describe('per-device elevated scopes', () => {
    const secret = 'cd'.repeat(32);
    const id = 'fedcba9876543210fedcba98';
    const token = `txd_${id}_${'y'.repeat(43)}`;
    const tokenHash = createHmac('sha256', Buffer.from(secret, 'hex'))
      .update(`device-token\0${token}`)
      .digest('hex');
    const registryWith = (scopes: string[], grantsVersion?: number) => ({
      schema_version: 1,
      devices: {
        [id]: {
          id,
          token_hash: tokenHash,
          scopes,
          ...(grantsVersion === undefined ? {} : { grants_version: grantsVersion }),
          expires_at: null,
          revoked_at: null,
        },
      },
    });

    it('honors index, agent and modify only on records the host explicitly granted', () => {
      const granted = registryWith(['chat', 'index', 'agent', 'modify'], 2);
      for (const scope of ['chat', 'index', 'agent', 'modify']) {
        expect(deviceTokenHasScope(token, scope, granted, secret)).toBe(true);
      }
      // Never grantable, even if a record claims them.
      const forged = registryWith(['system', 'agent_yolo'], 2);
      expect(deviceTokenHasScope(token, 'system', forged, secret)).toBe(false);
      expect(deviceTokenHasScope(token, 'agent_yolo', forged, secret)).toBe(false);
      // Scope not present in a granted record.
      expect(deviceTokenHasScope(token, 'agent', registryWith(['chat', 'index'], 2), secret)).toBe(false);
    });

    it('ignores elevated scopes on legacy records without the grants marker', () => {
      for (const legacy of [registryWith(['chat', 'index', 'agent', 'modify']), registryWith(['chat', 'agent'], 1)]) {
        expect(deviceTokenHasScope(token, 'chat', legacy, secret)).toBe(true);
        for (const scope of ['index', 'agent', 'modify']) {
          expect(deviceTokenHasScope(token, scope, legacy, secret)).toBe(false);
        }
      }
    });

    it('classifies only index, agent and modify as elevated', () => {
      expect(['index', 'agent', 'modify'].every(isElevatedDeviceScope)).toBe(true);
      expect(['chat', 'read_private', 'web', 'system', 'agent_yolo'].some(isElevatedDeviceScope)).toBe(false);
      expect(isElevatedDeviceScope(null)).toBe(false);
    });

    it('never lets an admin token unlock elevated scopes over the network', () => {
      const remote = '192.168.1.20';
      // Elevated: a valid remote admin token alone is not enough.
      expect(isAuthorizedScopedProxyPeer(remote, 'admin', 'admin', '', false, true)).toBe(false);
      // ...but a device the host granted the scope to still works.
      expect(isAuthorizedScopedProxyPeer(remote, 'admin', 'admin', token, true, true)).toBe(true);
      expect(isAuthorizedScopedProxyPeer(remote, 'admin', 'admin', token, false, true)).toBe(false);
      // A wrong admin credential is never rescued by a device token.
      expect(isAuthorizedScopedProxyPeer(remote, 'wrong', 'admin', token, true, true)).toBe(false);
      // The same operator on the host itself is unaffected, and so is a non-elevated scope.
      expect(isAuthorizedScopedProxyPeer('127.0.0.1', 'admin', 'admin', '', false, true)).toBe(true);
      expect(isAuthorizedScopedProxyPeer(remote, 'admin', 'admin', '', false, false)).toBe(true);
    });
  });
});
