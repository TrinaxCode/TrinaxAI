import { useEffect } from 'react';
import { audioManager } from '../services/audioManager';

export function useWaitingSound(active: boolean): void {
  useEffect(() => {
    if (!active) { audioManager.stop(); return undefined; }
    audioManager.play('generation-start');
    const timeout = window.setTimeout(() => audioManager.stop(), 8_000);
    return () => { window.clearTimeout(timeout); audioManager.stop(); };
  }, [active]);
}
