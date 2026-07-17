export const SOUND_ENABLED_KEY = 'tc-sound-effects';
export const SOUND_SETTING_EVENT = 'tc-sound-effects-change';

export type SoundEvent =
  | 'generation-start' | 'first-token' | 'response-complete' | 'error' | 'cancel'
  | 'stt-on' | 'stt-off' | 'call-enter' | 'call-exit'
  | 'tool-running' | 'tool-complete' | 'file-received' | 'file-processing'
  | 'file-ready' | 'agent-working' | 'confirmation';

type AudioContextConstructor = typeof AudioContext;

const NOTES: Record<SoundEvent, readonly number[]> = {
  'generation-start': [392, 523], 'first-token': [659], 'response-complete': [523, 659, 784],
  error: [220, 175], cancel: [330, 247], 'stt-on': [440, 659], 'stt-off': [659, 440],
  'call-enter': [392, 523, 659], 'call-exit': [659, 523, 392], 'tool-running': [330, 440],
  'tool-complete': [440, 587], 'file-received': [349, 523], 'file-processing': [294, 392],
  'file-ready': [523, 698], 'agent-working': [262, 330], confirmation: [587, 587],
};

class AudioManager {
  private context: AudioContext | null = null;
  private active: OscillatorNode[] = [];
  private lastPlayed = new Map<SoundEvent, number>();

  enabled(): boolean {
    try { return localStorage.getItem(SOUND_ENABLED_KEY) !== '0'; } catch { return true; }
  }

  setEnabled(enabled: boolean): void {
    try { localStorage.setItem(SOUND_ENABLED_KEY, enabled ? '1' : '0'); } catch { /* unavailable storage */ }
    if (!enabled) this.stop();
    window.dispatchEvent(new CustomEvent(SOUND_SETTING_EVENT, { detail: enabled }));
  }

  play(event: SoundEvent): void {
    if (!this.enabled()) return;
    const now = Date.now();
    if (now - (this.lastPlayed.get(event) ?? 0) < 300) return;
    this.lastPlayed.set(event, now);
    const Context = window.AudioContext
      || (window as typeof window & { webkitAudioContext?: AudioContextConstructor }).webkitAudioContext;
    if (!Context) return;
    try {
      this.context ??= new Context();
      void this.context.resume().then(() => this.playNotes(NOTES[event])).catch(() => undefined);
    } catch { /* sound effects are optional */ }
  }

  stop(): void {
    this.active.splice(0).forEach((oscillator) => { try { oscillator.stop(); } catch { /* already stopped */ } });
  }

  dispose(): void {
    this.stop();
    const context = this.context;
    this.context = null;
    if (context) void context.close().catch(() => undefined);
  }

  private playNotes(notes: readonly number[]): void {
    if (!this.context || !this.enabled()) return;
    this.stop();
    notes.forEach((frequency, index) => {
      const oscillator = this.context!.createOscillator();
      const gain = this.context!.createGain();
      const start = this.context!.currentTime + index * 0.09;
      oscillator.frequency.setValueAtTime(frequency, start);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.025, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.11);
      oscillator.connect(gain); gain.connect(this.context!.destination);
      this.active.push(oscillator);
      oscillator.addEventListener('ended', () => { this.active = this.active.filter((item) => item !== oscillator); }, { once: true });
      oscillator.start(start); oscillator.stop(start + 0.12);
    });
  }
}

export const audioManager = new AudioManager();

