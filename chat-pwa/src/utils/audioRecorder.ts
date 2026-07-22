/* Audio recorder with simple VAD (Voice Activity Detection) using Web Audio API.
   Grabadora de audio con VAD simple usando Web Audio API. */

export interface RecorderCallbacks {
  onStart?: () => void;
  onSilence: (blob: Blob) => void;
  onError: (err: Error) => void;
}

function selectMimeType(): string {
  const types = ['audio/webm', 'audio/mp4', 'audio/ogg', 'audio/wav'];
  for (const t of types) if (MediaRecorder.isTypeSupported(t)) return t;
  return '';
}

export interface AudioRecorder {
  stop: () => void;
  cancel: () => void;
}

let activeRecorder: AudioRecorder | null = null;
let pendingRecorder: Promise<AudioRecorder> | null = null;

export function stopAudioRecorder(): void {
  activeRecorder?.cancel();
  activeRecorder = null;
}

export function startAudioRecorder(
  callbacks: RecorderCallbacks,
  silenceMs = 1500,
  threshold = 0.015,
): Promise<AudioRecorder> {
  if (pendingRecorder) return pendingRecorder;
  stopAudioRecorder();
  pendingRecorder = createAudioRecorder(callbacks, silenceMs, threshold)
    .then((recorder) => {
      const wrapped: AudioRecorder = {
        stop: () => { recorder.stop(); if (activeRecorder === wrapped) activeRecorder = null; },
        cancel: () => { recorder.cancel(); if (activeRecorder === wrapped) activeRecorder = null; },
      };
      activeRecorder = wrapped;
      return wrapped;
    })
    .finally(() => { pendingRecorder = null; });
  return pendingRecorder;
}

async function createAudioRecorder(
  callbacks: RecorderCallbacks,
  silenceMs: number,
  threshold: number,
): Promise<AudioRecorder> {
  const mimeType = selectMimeType();
  if (!mimeType) throw new Error('noAudioMimeType');

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  let mediaRecorder: MediaRecorder;
  let audioCtx: AudioContext | undefined;
  let analyser: AnalyserNode;
  try {
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    audioCtx = new AudioContext();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    source.connect(analyser);
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

  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    if (startWatchdog) { clearTimeout(startWatchdog); startWatchdog = 0; }
    if (rafId) cancelAnimationFrame(rafId);
    void audioCtx.close().catch(() => undefined);
    audioTracks.forEach((track) => track.removeEventListener('ended', onTrackEnded));
    stream.getTracks().forEach((t) => t.stop());
  };

  const onTrackEnded = () => {
    if (cleaned || cancelled) return;
    cancelled = true;
    cleanup();
    callbacks.onError(new Error('microphoneDisconnected'));
  };
  audioTracks.forEach((track) => track.addEventListener('ended', onTrackEnded, { once: true }));

  mediaRecorder.onstop = () => {
    cleanup();
    if (cancelled) return;
    const blob = new Blob(chunks, { type: mimeType });
    callbacks.onSilence(blob);
  };

  mediaRecorder.onerror = () => {
    cancelled = true;
    cleanup();
    callbacks.onError(new Error('mediaRecorderError'));
  };

  const stop = () => {
    if (rafId) cancelAnimationFrame(rafId);
    try { mediaRecorder.stop(); } catch {}
    cleanup();
  };

  const cancel = () => {
    cancelled = true;
    stop();
  };

  const check = () => {
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
    if (startWatchdog) { clearTimeout(startWatchdog); startWatchdog = 0; }
    if (!started) {
      started = true;
      callbacks.onStart?.();
      rafId = window.requestAnimationFrame(check);
    }
  };

  mediaRecorder.start(200);

  // Safety net: if `onstart` never fires (permission/browser quirk), the mic
  // stream and AudioContext would stay open forever. Release them after 5s.
  startWatchdog = window.setTimeout(() => {
    if (!started && !cleaned) {
      cleanup();
      callbacks.onError(new Error('recorderStartTimeout'));
    }
  }, 5000);

  return { stop, cancel };
}
