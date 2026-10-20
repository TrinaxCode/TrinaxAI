import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePairedDeviceScope } from './usePairedDeviceScope';

const auth = vi.hoisted(() => ({ local: false, scopes: new Set<string>() }));
vi.mock('../lib/authHeaders', () => ({
  isLocalHostBrowser: () => auth.local,
  deviceSessionHasScope: (scope: string) => auth.local || auth.scopes.has(scope),
}));

describe('usePairedDeviceScope', () => {
  beforeEach(() => {
    auth.local = false;
    auth.scopes = new Set();
  });

  it('is true only for a paired device the host granted the scope to', () => {
    auth.scopes = new Set(['chat', 'index']);
    expect(renderHook(() => usePairedDeviceScope('index')).result.current).toBe(true);
    expect(renderHook(() => usePairedDeviceScope('agent')).result.current).toBe(false);
  });

  it('does not treat the localhost host as a paired device', () => {
    auth.local = true;
    expect(renderHook(() => usePairedDeviceScope('index')).result.current).toBe(false);
  });

  it('follows permission changes the host makes while the app is open', () => {
    auth.scopes = new Set(['chat']);
    const { result } = renderHook(() => usePairedDeviceScope('modify'));
    expect(result.current).toBe(false);

    act(() => {
      auth.scopes = new Set(['chat', 'modify']);
      window.dispatchEvent(new Event('trinaxai-device-auth-changed'));
    });
    expect(result.current).toBe(true);

    act(() => {
      auth.scopes = new Set(['chat']);
      window.dispatchEvent(new Event('trinaxai-device-auth-changed'));
    });
    expect(result.current).toBe(false);
  });
});
