import { createHmac, timingSafeEqual } from 'node:crypto';
import net from 'node:net';

const OLLAMA_PROXY_ALLOWLIST = new Map<string, ReadonlySet<string>>([
  ['/api/ollama/api/tags', new Set(['GET'])],
  ['/api/ollama/api/chat', new Set(['POST'])],
  ['/api/ollama/api/generate', new Set(['POST'])],
  ['/api/ollama/api/pull', new Set(['POST'])],
]);

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

export function constantTimeTokenEqual(left: string, right: string): boolean {
  const a = Buffer.from(left, 'utf8');
  const b = Buffer.from(right, 'utf8');
  return a.length === b.length && timingSafeEqual(a, b);
}

type DeviceRecord = {
  id?: unknown;
  token_hash?: unknown;
  scopes?: unknown;
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
): boolean {
  if (suppliedAdminToken) {
    return Boolean(
      configuredAdminToken
      && constantTimeTokenEqual(suppliedAdminToken, configuredAdminToken),
    );
  }
  if (suppliedDeviceToken) return deviceGrantsScope;
  return isLoopbackAddress(peer);
}

export function isAuthorizedSystemProxyPeer(
  peer: string,
  suppliedToken: string,
  configuredToken: string,
  allowLanWithoutToken: boolean,
): boolean {
  if (suppliedToken) {
    return Boolean(configuredToken && constantTimeTokenEqual(suppliedToken, configuredToken));
  }
  if (isLoopbackAddress(peer)) return true;
  // Once a credential exists it is mandatory for every remote peer.  The LAN
  // fallback is retained only for explicit legacy installations without one.
  return !configuredToken && allowLanWithoutToken && isPrivateLanAddress(peer);
}
