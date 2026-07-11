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
}

export async function startAudioRecorder(
  callbacks: RecorderCallbacks,
  silenceMs = 1500,
  threshold = 0.015,
): Promise<AudioRecorder> {
  const mimeType = selectMimeType();
  if (!mimeType) throw new Error('noAudioMimeType');

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mediaRecorder = new MediaRecorder(stream, { mimeType });
  const chunks: Blob[] = [];

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };

  const audioCtx = new AudioContext();
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  source.connect(analyser);
  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.3;

  const data = new Uint8Array(analyser.fftSize);
  let lastVoice = Date.now();
  let rafId = 0;
  let started = false;
  let cleaned = false;
  let startWatchdog = 0;

  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    if (startWatchdog) { clearTimeout(startWatchdog); startWatchdog = 0; }
    if (rafId) cancelAnimationFrame(rafId);
    void audioCtx.close().catch(() => undefined);
    stream.getTracks().forEach((t) => t.stop());
  };

  mediaRecorder.onstop = () => {
    cleanup();
    const blob = new Blob(chunks, { type: mimeType });
    callbacks.onSilence(blob);
  };

  mediaRecorder.onerror = () => {
    cleanup();
    callbacks.onError(new Error('mediaRecorderError'));
  };

  const stop = () => {
    if (rafId) cancelAnimationFrame(rafId);
    try { mediaRecorder.stop(); } catch {}
    cleanup();
  };

  const check = () => {
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length);
    if (rms > threshold) lastVoice = Date.now();

    if (Date.now() - lastVoice > silenceMs) {
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

  return { stop };
}
