/* Audio recorder with simple VAD (Voice Activity Detection) using Web Audio API.
   Grabadora de audio con VAD simple usando Web Audio API. */

export interface RecorderCallbacks {
  onStart?: () => void;
  onSilence: (blob: Blob) => void;
  onError: (err: Error) => void;
}

const DEFAULT_MAX_RECORDING_MS = 60_000;

function selectMimeType(): string {
  const types = ['audio/webm', 'audio/mp4', 'audio/ogg', 'audio/wav'];
  if (typeof MediaRecorder === 'undefined') return '';
  for (const t of types) {
    try {
      if (MediaRecorder.isTypeSupported(t)) return t;
    } catch { /* a browser may expose MediaRecorder without MIME probing */ }
  }
  return '';
}

export interface AudioRecorder {
  stop: () => void;
  cancel: () => void;
}

let activeRecorder: AudioRecorder | null = null;
let pendingRecorder: { cancelled: boolean } | null = null;

const NOOP_RECORDER: AudioRecorder = { stop: () => {}, cancel: () => {} };

function stopAudioRecorder(): void {
  activeRecorder?.cancel();
  activeRecorder = null;
  if (pendingRecorder) pendingRecorder.cancelled = true;
  pendingRecorder = null;
}

export function startAudioRecorder(
  callbacks: RecorderCallbacks,
  silenceMs = 1500,
  threshold = 0.015,
  maxDurationMs = DEFAULT_MAX_RECORDING_MS,
): Promise<AudioRecorder> {
  stopAudioRecorder();
  const pending = { cancelled: false };
  pendingRecorder = pending;
  const promise = createAudioRecorder(callbacks, silenceMs, threshold, maxDurationMs)
    .then((recorder) => {
      if (pending.cancelled) {
        recorder.cancel();
        return NOOP_RECORDER;
      }
      const wrapped: AudioRecorder = {
        stop: () => { recorder.stop(); if (activeRecorder === wrapped) activeRecorder = null; },
        cancel: () => { recorder.cancel(); if (activeRecorder === wrapped) activeRecorder = null; },
      };
      activeRecorder = wrapped;
      return wrapped;
    })
    .catch((error) => {
      if (pending.cancelled) return NOOP_RECORDER;
      throw error;
    })
    .finally(() => { if (pendingRecorder === pending) pendingRecorder = null; });
  return promise;
}

async function createAudioRecorder(
  callbacks: RecorderCallbacks,
  silenceMs: number,
  threshold: number,
  maxDurationMs: number,
): Promise<AudioRecorder> {
  const mimeType = selectMimeType();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  let mediaRecorder: MediaRecorder;
  let audioCtx: AudioContext | undefined;
  let analyser: AnalyserNode;
  try {
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const AudioContextCtor = window.AudioContext
      || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextCtor) throw new Error('audioContextUnsupported');
    audioCtx = new AudioContextCtor();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    source.connect(analyser);
    // Mobile browsers commonly create AudioContext in "suspended" state.
    // Without resuming it, the analyser receives zeros forever and VAD never
    // reaches silence after speech, leaving the call stuck on listening.
    if (typeof audioCtx.resume === 'function') await audioCtx.resume();
  } catch (error) {
    void audioCtx?.close().catch(() => undefined);
    stream.getTracks().forEach((track) => track.stop());
    throw error;
  }
  if (!audioCtx) throw new Error('audioContextInitializationFailed');
  const chunks: Blob[] = [];

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };

  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.3;

  const data = new Uint8Array(analyser.fftSize);
  const audioTracks = stream.getTracks().filter((track) => track.kind === 'audio');
  let lastVoice = Date.now();
  let heardVoice = false;
  let rafId = 0;
  let started = false;
  let cleaned = false;
  let cancelled = false;
  let startWatchdog = 0;
  let maxDurationTimer = 0;
  let stopRequested = false;
  let finished = false;

  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    if (startWatchdog) { clearTimeout(startWatchdog); startWatchdog = 0; }
    if (maxDurationTimer) { clearTimeout(maxDurationTimer); maxDurationTimer = 0; }
    if (rafId) cancelAnimationFrame(rafId);
    void audioCtx.close().catch(() => undefined);
    audioTracks.forEach((track) => track.removeEventListener('ended', onTrackEnded));
    stream.getTracks().forEach((t) => t.stop());
  };

  const finish = () => {
    if (finished) return false;
    finished = true;
    cleanup();
    return true;
  };

  const onTrackEnded = () => {
    if (finished || cleaned) return;
    cancelled = true;
    finish();
    callbacks.onError(new Error('microphoneDisconnected'));
  };
  audioTracks.forEach((track) => track.addEventListener('ended', onTrackEnded, { once: true }));

  mediaRecorder.onstop = () => {
    if (!finish() || cancelled) return;
    const blob = new Blob(chunks, { type: mimeType || mediaRecorder.mimeType || 'audio/webm' });
    callbacks.onSilence(blob);
  };

  mediaRecorder.onerror = () => {
    if (finished) return;
    cancelled = true;
    finish();
    callbacks.onError(new Error('mediaRecorderError'));
  };

  const stop = () => {
    if (finished || stopRequested) return;
    stopRequested = true;
    if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
    try { mediaRecorder.stop(); } catch {
      finish();
      return;
    }
    cleanup();
  };

  const cancel = () => {
    if (finished) return;
    cancelled = true;
    stop();
    finish();
  };

  const check = () => {
    if (finished || cleaned) return;
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length);
    if (rms > threshold) {
      heardVoice = true;
      lastVoice = Date.now();
    }

    if (heardVoice && Date.now() - lastVoice > silenceMs) {
      stop();
      return;
    }
    rafId = window.requestAnimationFrame(check);
  };

  mediaRecorder.onstart = () => {
    if (finished || cleaned) return;
    if (startWatchdog) { clearTimeout(startWatchdog); startWatchdog = 0; }
    if (!started) {
      started = true;
      callbacks.onStart?.();
      rafId = window.requestAnimationFrame(check);
      const duration = Number.isFinite(maxDurationMs) ? Math.max(1, maxDurationMs) : DEFAULT_MAX_RECORDING_MS;
      maxDurationTimer = window.setTimeout(() => {
        maxDurationTimer = 0;
        stop();
      }, duration);
    }
  };

  try {
    mediaRecorder.start(200);
  } catch (error) {
    cancelled = true;
    finish();
    throw error;
  }

  // Safety net: if `onstart` never fires (permission/browser quirk), the mic
  // stream and AudioContext would stay open forever. Release them after 5s.
  if (!started && !finished) {
    startWatchdog = window.setTimeout(() => {
      if (started || finished) return;
      cancelled = true;
      finish();
      callbacks.onError(new Error('recorderStartTimeout'));
    }, 5000);
  }

  return { stop, cancel };
}
