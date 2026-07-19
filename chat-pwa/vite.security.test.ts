import { describe, expect, it } from 'vitest';
import { createHmac } from 'node:crypto';

import {
  isAllowedOllamaProxyRequest,
  deviceTokenHasScope,
  isAuthorizedOllamaProxyPeer,
  isAuthorizedScopedProxyPeer,
  isAuthorizedSystemProxyPeer,
  isLoopbackAddress,
  isPrivateLanAddress,
} from './vite-security';

describe('Vite security boundary', () => {
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

  it('does not let the system-control LAN fallback bypass a configured token', () => {
    expect(isAuthorizedSystemProxyPeer('192.168.1.20', '', 'configured', true)).toBe(false);
    expect(isAuthorizedSystemProxyPeer('192.168.1.20', 'configured', 'configured', true)).toBe(true);
    expect(isAuthorizedSystemProxyPeer('192.168.1.20', '', '', true)).toBe(true);
    expect(isAuthorizedSystemProxyPeer('8.8.8.8', '', '', true)).toBe(false);
    expect(isAuthorizedSystemProxyPeer('127.0.0.1', '', 'configured', false)).toBe(true);
    expect(isAuthorizedSystemProxyPeer('127.0.0.1', 'wrong', 'configured', false)).toBe(false);
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
          scopes: ['chat', 'read_private'],
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
    expect(deviceTokenHasScope(`${token}bad`, 'chat', registry, secret)).toBe(false);
    registry.devices[id].revoked_at = 123;
    expect(deviceTokenHasScope(token, 'chat', registry, secret)).toBe(false);
  });
});
