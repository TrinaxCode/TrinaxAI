import { useEffect, useState } from 'react';

import { deviceSessionHasScope, isLocalHostBrowser } from '../lib/authHeaders';

function pairedDeviceHasScope(scope: string): boolean {
  return !isLocalHostBrowser() && deviceSessionHasScope(scope);
}

/**
 * Whether this browser is a paired device the host granted `scope` to. The
 * localhost host is not a paired device, so callers combine this with their
 * host capability (`canManageSystem || usePairedDeviceScope(...)`). It
 * re-evaluates when the pairing state refreshes, so a permission the host just
 * changed takes effect without a reload.
 */
export function usePairedDeviceScope(scope: string): boolean {
  const [granted, setGranted] = useState(() => pairedDeviceHasScope(scope));
  useEffect(() => {
    const sync = () => setGranted(pairedDeviceHasScope(scope));
    sync();
    window.addEventListener('trinaxai-device-auth-changed', sync);
    return () => window.removeEventListener('trinaxai-device-auth-changed', sync);
  }, [scope]);
  return granted;
}
