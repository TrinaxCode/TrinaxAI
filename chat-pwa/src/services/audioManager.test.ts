import { beforeEach, describe, expect, it, vi } from 'vitest';
import { audioManager, SOUND_ENABLED_KEY, SOUND_SETTING_EVENT } from './audioManager';

describe('audioManager', () => {
  beforeEach(() => { audioManager.dispose(); localStorage.clear(); vi.restoreAllMocks(); });

  it('persists changes and applies them immediately', () => {
    const changed = vi.fn();
    window.addEventListener(SOUND_SETTING_EVENT, changed, { once: true });
    audioManager.setEnabled(false);
    expect(localStorage.getItem(SOUND_ENABLED_KEY)).toBe('0');
    expect(audioManager.enabled()).toBe(false);
    expect(changed).toHaveBeenCalledOnce();
  });

  it('does not construct audio while disabled', () => {
    const Context = vi.fn();
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: Context });
    localStorage.setItem(SOUND_ENABLED_KEY, '0');
    audioManager.play('generation-start');
    expect(Context).not.toHaveBeenCalled();
  });
});
