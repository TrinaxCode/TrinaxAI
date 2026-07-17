/** Erase every browser-local TrinaxAI artifact after device revocation.
 * Server-side shared data is intentionally untouched for the main device.
 */
export const LOCAL_DEVICE_WIPE_EVENT = 'trinaxai-local-device-wipe';

export async function wipeRevokedDeviceData(): Promise<void> {
  // Cancel React-side debounced history writers before clearing storage.
  window.dispatchEvent(new Event(LOCAL_DEVICE_WIPE_EVENT));
  try { localStorage.clear(); } catch { /* unavailable */ }
  try { sessionStorage.clear(); } catch { /* unavailable */ }

  if (typeof indexedDB !== 'undefined') {
    // Current attachment store plus known historical names. deleteDatabase is
    // idempotent, so this also remains safe across upgrades.
    await Promise.allSettled([
      'trinaxai-chat-files',
      'trinaxai',
      'trinaxai-chat',
    ].map((name) => new Promise<void>((resolve) => {
      const request = indexedDB.deleteDatabase(name);
      request.onsuccess = () => resolve();
      request.onerror = () => resolve();
      request.onblocked = () => resolve();
    })));
  }

  if (typeof caches !== 'undefined') {
    try {
      const names = await caches.keys();
      await Promise.allSettled(names.map((name) => caches.delete(name)));
    } catch { /* cache storage unavailable */ }
  }

  if ('serviceWorker' in navigator) {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.allSettled(registrations.map((registration) => registration.unregister()));
    } catch { /* service workers unavailable */ }
  }

  // A mounted third-party/browser callback could have written while async
  // stores were being deleted. The final pass guarantees an empty handoff.
  try { localStorage.clear(); } catch { /* unavailable */ }
  try { sessionStorage.clear(); } catch { /* unavailable */ }
}
