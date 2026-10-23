import { createHmac, timingSafeEqual } from 'node:crypto';
import net from 'node:net';

const OLLAMA_PROXY_ALLOWLIST = new Map<string, ReadonlySet<string>>([
  ['/api/ollama/api/tags', new Set(['GET'])],
  ['/api/ollama/api/chat', new Set(['POST'])],
  ['/api/ollama/api/generate', new Set(['POST'])],
  ['/api/ollama/api/pull', new Set(['POST'])],
  ['/api/ollama/api/delete', new Set(['DELETE'])],
]);
/** Granted per device by the localhost operator; never by an admin token over the network. */
const ELEVATED_DEVICE_SCOPES = new Set(['index', 'agent', 'modify']);
const REMOTE_DEVICE_SCOPES = new Set(['chat', 'read_private', 'web', ...ELEVATED_DEVICE_SCOPES]);
/** Registry records at or above this version may carry elevated scopes. */
const ELEVATED_GRANTS_VERSION = 2;
export const DEVICE_TOKEN_COOKIE = 'trinaxai-device-token';

/** Extract the exact device cookie without exposing any other cookie values. */
export function deviceTokenFromCookie(header: string | undefined): string {
  if (!header) return '';
  for (const part of header.split(';')) {
    const separator = part.indexOf('=');
    if (separator < 0 || part.slice(0, separator).trim() !== DEVICE_TOKEN_COOKIE) continue;
    const value = part.slice(separator + 1).trim();
    if (!value) return '';
    try { return decodeURIComponent(value); } catch { return ''; }
  }
  return '';
}

export function normalizeAddress(host: string): string {
  return host.replace(/^::ffff:/, '');
}

export function isLoopbackAddress(host: string): boolean {
  const clean = normalizeAddress(host);
  if (clean === '::1' || clean === 'localhost') return true;
  if (net.isIPv4(clean)) return clean.startsWith('127.');
  return false;
}

export function isPrivateLanAddress(host: string): boolean {
  const clean = normalizeAddress(host).toLowerCase();
  if (isLoopbackAddress(clean)) return true;
  if (net.isIPv4(clean)) {
    if (clean.startsWith('10.') || clean.startsWith('192.168.')) return true;
    const parts = clean.split('.').map((part) => Number(part));
    return parts.length === 4 && parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31;
  }
  if (!net.isIPv6(clean)) return false;
  return clean.startsWith('fe8') || clean.startsWith('fe9')
    || clean.startsWith('fea') || clean.startsWith('feb')
    || clean.startsWith('fc') || clean.startsWith('fd');
}

export function isAllowedOllamaProxyRequest(method: string, pathname: string): boolean {
  return OLLAMA_PROXY_ALLOWLIST.get(pathname)?.has(method.toUpperCase()) ?? false;
}

export function isElevatedDeviceScope(scope: string | null): boolean {
  return scope !== null && ELEVATED_DEVICE_SCOPES.has(scope);
}

export function requiredOllamaProxyScope(pathname: string): 'chat' | 'system' {
  return pathname === '/api/ollama/api/pull' || pathname === '/api/ollama/api/delete'
    ? 'system'
    : 'chat';
}

/** Map RAG API areas to the scope required by a remote paired device. */
export function requiredRagProxyScope(pathname: string, method = 'GET'): string | null {
  const verb = method.toUpperCase();
  if (pathname === '/api/rag/health' || pathname === '/api/rag/resources') return null;
  if (pathname === '/api/rag/v1/pairing/claim' || pathname === '/api/rag/v1/pairing/me' || pathname === '/api/rag/v1/pairing/new-device') return null;
  if (pathname === '/api/rag/v1/pairing/start' || pathname === '/api/rag/v1/pairing/devices') return 'system';
  if (pathname.startsWith('/api/rag/v1/pairing/devices/')) return 'system';
  if (pathname.startsWith('/api/rag/v1/agent')) return 'agent';
  if (pathname.startsWith('/api/rag/system/index') || pathname.startsWith('/api/rag/v1/watch/')) return 'index';
  if (pathname.startsWith('/api/rag/system/')) return 'system';
  if (pathname.startsWith('/api/rag/collections')) return verb === 'GET' ? 'read_private' : 'index';
  if (pathname.startsWith('/api/rag/v1/sources')) return verb === 'DELETE' ? 'index' : 'read_private';
  if (pathname.startsWith('/api/rag/attachments')) {
    if (pathname.endsWith('/open')) return 'system';
    return verb === 'DELETE' ? 'modify' : 'read_private';
  }
  if (pathname.startsWith('/api/rag/v1/memory')) return verb === 'GET' || (verb === 'POST' && pathname.endsWith('/context')) ? 'read_private' : 'modify';
  if (pathname === '/api/rag/app-state' || pathname.startsWith('/api/rag/v1/stats')) return verb === 'DELETE' ? 'system' : 'read_private';
  if (pathname.startsWith('/api/rag/v1/settings/web-search')) return 'modify';
  if (pathname.startsWith('/api/rag/v1/settings')) return 'system';
  if (pathname.startsWith('/api/rag/v1/usage') || pathname.startsWith('/api/rag/v1/chat') || pathname.startsWith('/api/rag/v1/research') || pathname.startsWith('/api/rag/v1/voice') || pathname.startsWith('/api/rag/documents')) return 'chat';
  return 'system';
}

export function needsInferenceLock(pathname: string): boolean {
  return pathname !== '/api/ollama/api/tags';
}

export function constantTimeTokenEqual(left: string, right: string): boolean {
  const a = Buffer.from(left, 'utf8');
  const b = Buffer.from(right, 'utf8');
  return a.length === b.length && timingSafeEqual(a, b);
}

type DeviceRecord = {
  id?: unknown;
  token_hash?: unknown;
  scopes?: unknown;
  grants_version?: unknown;
  expires_at?: unknown;
  revoked_at?: unknown;
};

/** Validate the Python-owned atomic registry without ever exposing its hashes. */
export function deviceTokenHasScope(
  token: string,
  requiredScope: string,
  registry: unknown,
  secretHex: string,
  nowSeconds = Date.now() / 1000,
): boolean {
  if (!REMOTE_DEVICE_SCOPES.has(requiredScope)) return false;
  const match = /^txd_([0-9a-f]{24})_([A-Za-z0-9_-]{40,})$/.exec(token.trim());
  if (!match || !/^[0-9a-fA-F]{64,}$/.test(secretHex)) return false;
  if (!registry || typeof registry !== 'object') return false;
  const document = registry as { schema_version?: unknown; devices?: unknown };
  if (document.schema_version !== 1 || !document.devices || typeof document.devices !== 'object') return false;
  const record = (document.devices as Record<string, DeviceRecord>)[match[1]];
  if (!record || record.id !== match[1] || typeof record.token_hash !== 'string') return false;
  if (record.revoked_at !== null && record.revoked_at !== undefined) return false;
  if (record.expires_at !== null && record.expires_at !== undefined) {
    if (typeof record.expires_at !== 'number' || record.expires_at <= nowSeconds) return false;
  }
  if (!Array.isArray(record.scopes) || !record.scopes.includes(requiredScope)) return false;
  // Records from before per-device grants never regain elevated scopes silently.
  if (ELEVATED_DEVICE_SCOPES.has(requiredScope) && record.grants_version !== ELEVATED_GRANTS_VERSION) return false;
  try {
    const secret = Buffer.from(secretHex, 'hex');
    if (secret.length < 32) return false;
    const actual = createHmac('sha256', secret)
      .update(`device-token\0${token}`, 'utf8')
      .digest('hex');
    return constantTimeTokenEqual(actual, record.token_hash);
  } catch {
    return false;
  }
}

export function isAuthorizedOllamaProxyPeer(
  peer: string,
  suppliedToken: string,
  configuredToken: string,
): boolean {
  if (suppliedToken) {
    return Boolean(configuredToken && constantTimeTokenEqual(suppliedToken, configuredToken));
  }
  return isLoopbackAddress(peer);
}

export function isAuthorizedScopedProxyPeer(
  peer: string,
  suppliedAdminToken: string,
  configuredAdminToken: string,
  suppliedDeviceToken: string,
  deviceGrantsScope: boolean,
  elevated = false,
): boolean {
  if (suppliedAdminToken) {
    const adminMatches = Boolean(
      configuredAdminToken
      && constantTimeTokenEqual(suppliedAdminToken, configuredAdminToken),
    );
    // A wrong admin credential is never rescued by a device token, and a right
    // one does not unlock per-device elevated scopes over the network.
    if (!adminMatches || !elevated || isLoopbackAddress(peer)) return adminMatches;
  }
  if (suppliedDeviceToken) return deviceGrantsScope;
  return isLoopbackAddress(peer);
}

export function isAuthorizedSystemProxyPeer(peer: string): boolean {
  return isLoopbackAddress(peer);
}

/**
 * Reject a Host header that names a foreign DNS domain (DNS rebinding).
 *
 * IP literals, single-label names (`localhost`), `*.localhost` and mDNS
 * `*.local` names cannot be served by a remote attacker's DNS. Any other name
 * must be listed in `TRINAXAI_ALLOWED_HOSTS` (comma-separated, `*` allows all).
 */
export function isTrustedHostHeader(hostHeader: string | undefined, allowedHosts = ''): boolean {
  if (!hostHeader) return true;
  const configured = new Set(
    allowedHosts.split(',').map((item) => item.trim().toLowerCase().replace(/\.$/, '')).filter(Boolean),
  );
  if (configured.has('*')) return true;
  let hostname = hostHeader.trim().toLowerCase();
  if (hostname.startsWith('[')) {
    const end = hostname.indexOf(']');
    hostname = end > 0 ? hostname.slice(1, end) : '';
  } else if (hostname.split(':').length === 2) {
    hostname = hostname.split(':', 1)[0];
  }
  hostname = hostname.replace(/\.$/, '');
  if (!hostname) return false;
  if (net.isIP(hostname)) return true;
  if (!hostname.includes('.') || hostname.endsWith('.localhost') || hostname.endsWith('.local')) return true;
  return configured.has(hostname);
}
