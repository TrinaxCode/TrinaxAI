export const SOUND_ENABLED_KEY = 'tc-sound-effects';
export const SOUND_SETTING_EVENT = 'tc-sound-effects-change';

export type SoundEvent =
  | 'generation-start' | 'first-token' | 'response-complete' | 'error' | 'cancel'
  | 'stt-on' | 'stt-off' | 'call-enter' | 'call-exit'
  | 'tool-running' | 'tool-complete' | 'file-received' | 'file-processing'
  | 'file-ready' | 'agent-working' | 'confirmation' | 'message-send'
  | 'notification-success' | 'notification-error' | 'notification-warning' | 'notification-info';

type AudioContextConstructor = typeof AudioContext;

type SoundProfile = {
  notes: readonly number[];
  waveform: OscillatorType;
  volume: number;
  noteLength: number;
  gap: number;
  replace?: boolean;
};

const SOUNDS: Record<SoundEvent, SoundProfile> = {
  'generation-start': { notes: [392, 523], waveform: 'sine', volume: 0.035, noteLength: 0.16, gap: 0.1, replace: true },
  'first-token': { notes: [659], waveform: 'sine', volume: 0.025, noteLength: 0.14, gap: 0 },
  'response-complete': { notes: [523, 659, 784], waveform: 'sine', volume: 0.035, noteLength: 0.16, gap: 0.08 },
  error: { notes: [220, 175], waveform: 'triangle', volume: 0.04, noteLength: 0.18, gap: 0.1 },
  cancel: { notes: [330, 247], waveform: 'triangle', volume: 0.03, noteLength: 0.12, gap: 0.07 },
  'stt-on': { notes: [440, 659], waveform: 'sine', volume: 0.03, noteLength: 0.13, gap: 0.07 },
  'stt-off': { notes: [659, 440], waveform: 'sine', volume: 0.025, noteLength: 0.13, gap: 0.07 },
  'call-enter': { notes: [392, 523, 659], waveform: 'sine', volume: 0.035, noteLength: 0.14, gap: 0.07, replace: true },
  'call-exit': { notes: [659, 523, 392], waveform: 'sine', volume: 0.03, noteLength: 0.14, gap: 0.07 },
  'tool-running': { notes: [330, 440], waveform: 'square', volume: 0.018, noteLength: 0.1, gap: 0.06 },
  'tool-complete': { notes: [440, 587], waveform: 'sine', volume: 0.03, noteLength: 0.13, gap: 0.07 },
  'file-received': { notes: [349, 523], waveform: 'triangle', volume: 0.028, noteLength: 0.12, gap: 0.07 },
  'file-processing': { notes: [294, 392], waveform: 'square', volume: 0.016, noteLength: 0.11, gap: 0.07 },
  'file-ready': { notes: [523, 698], waveform: 'sine', volume: 0.032, noteLength: 0.14, gap: 0.08 },
  'agent-working': { notes: [262, 330], waveform: 'triangle', volume: 0.018, noteLength: 0.14, gap: 0.08, replace: true },
  confirmation: { notes: [587, 587], waveform: 'sine', volume: 0.025, noteLength: 0.1, gap: 0.06 },
  'message-send': { notes: [392, 587], waveform: 'sine', volume: 0.028, noteLength: 0.1, gap: 0.06 },
  'notification-success': { notes: [587, 784], waveform: 'sine', volume: 0.028, noteLength: 0.12, gap: 0.07 },
  'notification-error': { notes: [196, 147], waveform: 'triangle', volume: 0.035, noteLength: 0.16, gap: 0.09 },
  'notification-warning': { notes: [392, 330], waveform: 'triangle', volume: 0.025, noteLength: 0.13, gap: 0.08 },
  'notification-info': { notes: [440], waveform: 'sine', volume: 0.018, noteLength: 0.11, gap: 0 },
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
    if (now - (this.lastPlayed.get(event) ?? 0) < 180) return;
    this.lastPlayed.set(event, now);
    const Context = window.AudioContext
      || (window as typeof window & { webkitAudioContext?: AudioContextConstructor }).webkitAudioContext;
    if (!Context) return;
    try {
      this.context ??= new Context();
      void this.context.resume().then(() => this.playNotes(SOUNDS[event])).catch(() => undefined);
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

  private playNotes(sound: SoundProfile): void {
    if (!this.context || !this.enabled()) return;
    if (sound.replace) this.stop();
    // Keep short cues clearly audible on laptop and mobile speakers.
    const volume = Math.min(sound.volume * 6, 0.3);
    sound.notes.forEach((frequency, index) => {
      const oscillator = this.context!.createOscillator();
      const gain = this.context!.createGain();
      const start = this.context!.currentTime + index * sound.gap;
      oscillator.frequency.setValueAtTime(frequency, start);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(volume, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + sound.noteLength);
      oscillator.type = sound.waveform;
      oscillator.connect(gain); gain.connect(this.context!.destination);
      this.active.push(oscillator);
      oscillator.addEventListener('ended', () => { this.active = this.active.filter((item) => item !== oscillator); }, { once: true });
      oscillator.start(start); oscillator.stop(start + sound.noteLength + 0.01);
    });
  }
}

export const audioManager = new AudioManager();
