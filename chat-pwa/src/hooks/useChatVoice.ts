import { useCallback, useEffect, useRef, useState, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from 'react';
import { startAudioRecorder, type AudioRecorder } from '../utils/audioRecorder';
import { audioManager } from '../services/audioManager';
import { detectBackendVoice, detectSpeechRecognition, detectSpeechSynthesis, shouldStopBackendVoice, speakBackend, stopBackendSpeech, takeSpeechChunk, transcribeAudio } from '../services/voice';
import type { ToastOptions } from '../components/Toast';
import type { TranslationKey } from '../i18n/translations';
import type { ChatMessage } from '../lib/api';
import type { AttachedDocument } from '../components/chat/types';

export type PendingImage = { dataUrl: string; file: File };

export type ChatSendOptions = {
  viaVoice?: boolean;
  continueCall?: boolean;
  imageOverride?: PendingImage;
  documentsOverride?: AttachedDocument[];
  baseMessages?: ChatMessage[];
};

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastApi {
  toast: (message: string, type?: ToastType, options?: ToastOptions) => void;
}

interface UseChatVoiceOptions {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  setInput: Dispatch<SetStateAction<string>>;
  sendTextRef: MutableRefObject<(raw: string, opts?: ChatSendOptions) => Promise<void>>;
  streaming: boolean;
  t: (key: TranslationKey) => string;
  toast: ToastApi;
  voiceLang: string;
}

export function useChatVoice({
  inputRef,
  setInput,
  sendTextRef,
  streaming,
  t,
  toast,
  voiceLang,
}: UseChatVoiceOptions) {
  const [listening, setListening] = useState(false);
  const listeningRef = useRef(false);
  const [callMode, setCallMode] = useState(false);
  const callModeRef = useRef(false);
  const recognitionRef = useRef<any>(null);
  const manualDictationRef = useRef(false);
  const startVoiceRef = useRef<(continuous: boolean, submit?: boolean) => void>(() => {});
  const voiceRestartTimerRef = useRef<number | null>(null);
  const recognitionRunRef = useRef(0);
  const ttsActiveKeyRef = useRef<string | null>(null);
  const [ttsActiveKey, setTtsActiveKey] = useState<string | null>(null);
  const [ttsSpeaking, setTtsSpeaking] = useState(false);
  const [voiceVersion, setVoiceVersion] = useState(0);
  const ttsTailRef = useRef('');
  const ttsQueueRef = useRef<string[]>([]);
  const ttsSpeakingRef = useRef(false);
  const ttsSourceDoneRef = useRef(false);
  const ttsEndRef = useRef<(() => void) | null>(null);
  const ttsPumpRef = useRef<number | null>(null);
  const ttsRunRef = useRef(0);
  const voiceToastAtRef = useRef(0);
  const ttsCancellingRef = useRef(false);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const wakeLockRequestRef = useRef(0);
  const backendRecorderRef = useRef<AudioRecorder | null>(null);
  const backendRecorderRunRef = useRef(0);
  const backendVoiceRetryRef = useRef(0);
  const backendTranscriptionAbortRef = useRef<AbortController | null>(null);
  const voiceSupported = detectSpeechRecognition();
  const secureVoiceContext = typeof window !== 'undefined'
    && (window.isSecureContext || ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname));

  const showVoiceToast = useCallback((message: string, type: 'warning' | 'error' = 'warning') => {
    const now = Date.now();
    if (now - voiceToastAtRef.current < 1800) return;
    voiceToastAtRef.current = now;
    toast.toast(message, type);
  }, [toast]);

  useEffect(() => {
    callModeRef.current = callMode;
  }, [callMode]);

  useEffect(() => {
    listeningRef.current = listening;
  }, [listening]);

  const requestWakeLock = useCallback(async () => {
    const requestId = ++wakeLockRequestRef.current;
    try {
      const sentinel = await (navigator as any).wakeLock?.request?.('screen');
      if (!sentinel) return;
      if (requestId !== wakeLockRequestRef.current) {
        await sentinel.release();
        return;
      }
      wakeLockRef.current = sentinel;
    } catch { /* ignore */ }
  }, []);

  const releaseWakeLock = useCallback(() => {
    wakeLockRequestRef.current += 1;
    const sentinel = wakeLockRef.current;
    wakeLockRef.current = null;
    sentinel?.release().catch(() => {});
  }, []);

  const queueVoiceRestart = useCallback((delay: number, manual = false) => {
    if (!callModeRef.current && !manualDictationRef.current) return;
    if (voiceRestartTimerRef.current !== null) window.clearTimeout(voiceRestartTimerRef.current);
    voiceRestartTimerRef.current = window.setTimeout(() => {
      voiceRestartTimerRef.current = null;
      if (callModeRef.current) startVoiceRef.current(true, true);
      else if (manualDictationRef.current && manual) startVoiceRef.current(false, false);
    }, delay);
  }, []);

  const startBackendVoiceCapture = useCallback(async (continuous: boolean, submit = true) => {
    if (!detectBackendVoice()) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      setCallMode(false);
      callModeRef.current = false;
      setListening(false);
      releaseWakeLock();
      return;
    }
    if (streaming) {
      if (continuous && callModeRef.current) queueVoiceRestart(300);
      else if (!continuous && manualDictationRef.current) queueVoiceRestart(300, true);
      return;
    }
    const runId = ++backendRecorderRunRef.current;
    const queueBackendRetry = (delay: number, manual = false) => {
      backendVoiceRetryRef.current += 1;
      if (shouldStopBackendVoice(backendVoiceRetryRef.current)) {
        if (continuous) {
          setCallMode(false);
          callModeRef.current = false;
        } else {
          manualDictationRef.current = false;
        }
        releaseWakeLock();
        showVoiceToast(t('voiceTooManyRetries'), 'warning');
        return;
      }
      queueVoiceRestart(delay, manual);
    };
    backendRecorderRef.current?.cancel();
    backendRecorderRef.current = null;
    backendTranscriptionAbortRef.current?.abort();
    backendTranscriptionAbortRef.current = null;
    try {
      const recorder = await startAudioRecorder({
        onStart: () => { if (runId === backendRecorderRunRef.current) setListening(true); },
        onSilence: async (blob) => {
          if (runId !== backendRecorderRunRef.current) return;
          backendRecorderRef.current = null;
          if (continuous && !callModeRef.current) return;
          setListening(false);
          const transcriptionController = new AbortController();
          backendTranscriptionAbortRef.current?.abort();
          backendTranscriptionAbortRef.current = transcriptionController;
          try {
            const text = await transcribeAudio(blob, voiceLang, transcriptionController.signal);
            if (runId !== backendRecorderRunRef.current || (continuous && !callModeRef.current)) return;
            backendVoiceRetryRef.current = 0;
            if (text.trim() && submit) {
              void sendTextRef.current(text.trim(), { viaVoice: true, continueCall: continuous });
            } else if (text.trim()) {
              setInput((previous) => `${previous ? `${previous} ` : ''}${text.trim()}`);
              inputRef.current?.focus();
              if (manualDictationRef.current) queueVoiceRestart(500, true);
            } else if (continuous && callModeRef.current) {
              queueVoiceRestart(500);
            } else if (manualDictationRef.current) {
              queueVoiceRestart(500, true);
            }
          } catch {
            if (transcriptionController.signal.aborted || runId !== backendRecorderRunRef.current) return;
            showVoiceToast(t('voiceRecognitionFailed'), 'warning');
            if (continuous && callModeRef.current) queueBackendRetry(900);
            else if (manualDictationRef.current) queueBackendRetry(900, true);
          } finally {
            if (backendTranscriptionAbortRef.current === transcriptionController) backendTranscriptionAbortRef.current = null;
          }
        },
        onError: (error) => {
          if (runId !== backendRecorderRunRef.current) return;
          setListening(false);
          backendRecorderRef.current = null;
          const permissionDenied = ['NotAllowedError', 'SecurityError'].includes(error.name);
          showVoiceToast(permissionDenied ? t('voiceMicPermissionDenied') : t('voiceRecognitionFailed'), permissionDenied ? 'error' : 'warning');
          if (permissionDenied) {
            setCallMode(false);
            callModeRef.current = false;
            manualDictationRef.current = false;
            releaseWakeLock();
          } else if (continuous && callModeRef.current) queueBackendRetry(1200);
          else if (manualDictationRef.current) queueBackendRetry(1200, true);
        },
      }, 2200);
      if (runId !== backendRecorderRunRef.current || (continuous && !callModeRef.current) || (!continuous && !manualDictationRef.current)) {
        recorder.cancel();
        return;
      }
      backendRecorderRef.current = recorder;
    } catch (err: unknown) {
      if (runId !== backendRecorderRunRef.current) return;
      setListening(false);
      const permissionDenied = err instanceof DOMException && ['NotAllowedError', 'SecurityError'].includes(err.name);
      showVoiceToast(permissionDenied ? t('voiceMicPermissionDenied') : t('voiceRecognitionFailed'), permissionDenied ? 'error' : 'warning');
      if (permissionDenied) {
        setCallMode(false);
        callModeRef.current = false;
        manualDictationRef.current = false;
        releaseWakeLock();
      } else if (continuous && callModeRef.current) queueBackendRetry(1200);
      else if (manualDictationRef.current) queueBackendRetry(1200, true);
    }
  }, [inputRef, queueVoiceRestart, releaseWakeLock, sendTextRef, setInput, showVoiceToast, streaming, t, voiceLang]);

  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  useEffect(() => {
    if (!ttsSupported) return undefined;
    const refreshVoices = () => setVoiceVersion((value) => value + 1);
    window.speechSynthesis.getVoices();
    window.speechSynthesis.addEventListener?.('voiceschanged', refreshVoices);
    const id = window.setTimeout(refreshVoices, 300);
    return () => {
      window.clearTimeout(id);
      window.speechSynthesis.removeEventListener?.('voiceschanged', refreshVoices);
    };
  }, [ttsSupported]);

  const pickVoice = useCallback(() => {
    if (!ttsSupported) return undefined;
    const voices = window.speechSynthesis.getVoices();
    const baseLang = voiceLang.slice(0, 2);
    return voices.find((vo) => vo.lang === voiceLang)
      || voices.find((vo) => vo.lang.toLowerCase().startsWith(baseLang))
      || voices[0];
  }, [ttsSupported, voiceLang, voiceVersion]);

  const splitSpeech = useCallback((text: string) => {
    const chunks: string[] = [];
    let rest = text.trim();
    while (rest.length > 0) {
      if (rest.length <= 220) {
        chunks.push(rest);
        break;
      }
      const cut = Math.max(
        rest.lastIndexOf('. ', 220),
        rest.lastIndexOf('? ', 220),
        rest.lastIndexOf('! ', 220),
        rest.lastIndexOf(', ', 180),
        180,
      );
      chunks.push(rest.slice(0, cut + 1).trim());
      rest = rest.slice(cut + 1).trim();
    }
    return chunks;
  }, []);

  const clearTtsState = useCallback(() => {
    ttsActiveKeyRef.current = null;
    setTtsActiveKey(null);
    ttsTailRef.current = '';
    ttsQueueRef.current = [];
    ttsSourceDoneRef.current = false;
    ttsSpeakingRef.current = false;
    setTtsSpeaking(false);
    ttsEndRef.current = null;
  }, []);

  const stopTtsPump = useCallback(() => {
    if (ttsPumpRef.current != null) {
      window.clearInterval(ttsPumpRef.current);
      ttsPumpRef.current = null;
    }
  }, []);

  const startTtsPump = useCallback(() => {
    stopTtsPump();
    ttsPumpRef.current = window.setInterval(() => {
      if (!ttsSupported || !ttsSpeakingRef.current) {
        stopTtsPump();
        return;
      }
      window.speechSynthesis.resume();
    }, 7000);
  }, [stopTtsPump, ttsSupported]);

  useEffect(() => () => stopTtsPump(), [stopTtsPump]);

  const cleanupVoiceResources = useCallback(() => {
    callModeRef.current = false;
    manualDictationRef.current = false;
    ttsRunRef.current += 1;
    ttsQueueRef.current = [];
    ttsTailRef.current = '';
    ttsSourceDoneRef.current = false;
    recognitionRunRef.current += 1;
    if (voiceRestartTimerRef.current !== null) {
      window.clearTimeout(voiceRestartTimerRef.current);
      voiceRestartTimerRef.current = null;
    }
    try { recognitionRef.current?.abort?.(); } catch { /* ignore */ }
    recognitionRef.current = null;
    backendRecorderRunRef.current += 1;
    backendRecorderRef.current?.cancel();
    backendRecorderRef.current = null;
    backendTranscriptionAbortRef.current?.abort();
    backendTranscriptionAbortRef.current = null;
    releaseWakeLock();
    stopTtsPump();
    try {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    } catch { /* ignore */ }
    stopBackendSpeech();
  }, [releaseWakeLock, stopTtsPump]);

  useEffect(() => () => cleanupVoiceResources(), [cleanupVoiceResources]);

  const stopSpeak = useCallback(() => {
    ttsCancellingRef.current = true;
    ttsRunRef.current += 1;
    if (ttsSupported) window.speechSynthesis.cancel();
    stopTtsPump();
    stopBackendSpeech();
    clearTtsState();
    window.setTimeout(() => { ttsCancellingRef.current = false; }, 200);
  }, [clearTtsState, stopTtsPump, ttsSupported]);

  const finishCallSpeech = useCallback((runId: number) => {
    if (runId !== ttsRunRef.current) return;
    stopTtsPump();
    ttsActiveKeyRef.current = null;
    setTtsActiveKey(null);
    ttsSpeakingRef.current = false;
    setTtsSpeaking(false);
    const done = ttsEndRef.current;
    ttsEndRef.current = null;
    ttsSourceDoneRef.current = false;
    done?.();
  }, [stopTtsPump]);

  const pumpCallSpeech = useCallback(() => {
    if (ttsSpeakingRef.current) return;
    const next = ttsQueueRef.current.shift();
    if (!next) {
      if (ttsSourceDoneRef.current) finishCallSpeech(ttsRunRef.current);
      return;
    }
    const runId = ttsRunRef.current;
    ttsSpeakingRef.current = true;
    setTtsSpeaking(true);
    startTtsPump();
    const onComplete = () => {
      if (runId !== ttsRunRef.current) return;
      ttsSpeakingRef.current = false;
      if (ttsQueueRef.current.length || ttsSourceDoneRef.current) pumpCallSpeech();
      else setTtsSpeaking(false);
    };
    if (detectSpeechSynthesis()) {
      const utterance = new SpeechSynthesisUtterance(next);
      utterance.lang = voiceLang;
      utterance.rate = 1.04;
      utterance.pitch = 1;
      utterance.volume = 1;
      const voice = pickVoice();
      if (voice) utterance.voice = voice;
      utterance.onend = onComplete;
      utterance.onerror = () => {
        if (runId !== ttsRunRef.current) return;
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        onComplete();
      };
      try {
        window.speechSynthesis.resume();
        window.speechSynthesis.speak(utterance);
      } catch {
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        onComplete();
      }
      return;
    }
    void speakBackend({
      text: next,
      lang: voiceLang,
      onEnded: onComplete,
      onError: () => {
        if (runId !== ttsRunRef.current) return;
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        onComplete();
      },
    }).catch(() => {
      if (runId !== ttsRunRef.current) return;
      if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
      onComplete();
    });
  }, [finishCallSpeech, pickVoice, showVoiceToast, startTtsPump, t, voiceLang]);

  const cleanSpeechText = useCallback((text: string) => text
    .replace(/```[\s\S]*?```/g, t('ttsCodeBlockReplacement'))
    .replace(/`[^`]*`/g, '')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/[#*_>~|]/g, '')
    .replace(/\s+/g, ' ')
    .trim(), [t]);

  const flushVoiceTts = useCallback((force = false, onDone?: () => void) => {
    let pending = ttsTailRef.current;
    while (pending) {
      const next = takeSpeechChunk(pending, force);
      if (!next.chunk) {
        pending = next.remainder;
        break;
      }
      const clean = cleanSpeechText(next.chunk);
      if (clean) ttsQueueRef.current.push(clean);
      pending = next.remainder;
      if (!force && !pending) break;
    }
    ttsTailRef.current = pending;
    if (force) {
      ttsSourceDoneRef.current = true;
      if (onDone) ttsEndRef.current = onDone;
    }
    pumpCallSpeech();
  }, [cleanSpeechText, pumpCallSpeech]);

  const unlockSpeech = useCallback(() => {
    if (!ttsSupported) return;
    try {
      window.speechSynthesis.resume();
      const utterance = new SpeechSynthesisUtterance('.');
      utterance.lang = voiceLang;
      utterance.volume = 0.01;
      utterance.rate = 1.2;
      window.speechSynthesis.speak(utterance);
      window.setTimeout(() => {
        if (!ttsSpeakingRef.current) window.speechSynthesis.cancel();
        window.speechSynthesis.resume();
      }, 120);
    } catch {
      showVoiceToast(t('ttsUnavailable'));
    }
  }, [showVoiceToast, t, ttsSupported, voiceLang]);

  const speak = useCallback((text: string, onDone?: () => void, key?: string) => {
    if (!ttsSupported || !text) {
      onDone?.();
      return;
    }
    if (key && ttsActiveKeyRef.current === key && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
      stopSpeak();
      return;
    }
    ttsCancellingRef.current = false;
    const runId = ++ttsRunRef.current;
    const clean = cleanSpeechText(text);
    window.speechSynthesis.cancel();
    stopBackendSpeech();
    window.speechSynthesis.resume();
    ttsActiveKeyRef.current = key ?? null;
    setTtsActiveKey(key ?? null);
    ttsSpeakingRef.current = true;
    setTtsSpeaking(true);
    startTtsPump();
    const voice = pickVoice();
    const parts = splitSpeech(clean);
    let completed = false;
    const finish = () => {
      if (completed || runId !== ttsRunRef.current) return;
      completed = true;
      stopTtsPump();
      clearTtsState();
      onDone?.();
    };
    if (parts.length === 0) {
      finish();
      return;
    }
    parts.forEach((part, index) => {
      const utterance = new SpeechSynthesisUtterance(part);
      utterance.lang = voiceLang;
      utterance.rate = 1.04;
      utterance.pitch = 1;
      utterance.volume = 1;
      if (voice) utterance.voice = voice;
      if (index === parts.length - 1) utterance.onend = finish;
      utterance.onerror = () => {
        if (completed || runId !== ttsRunRef.current) return;
        window.speechSynthesis.cancel();
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        finish();
      };
      try {
        window.speechSynthesis.speak(utterance);
      } catch {
        if (completed || runId !== ttsRunRef.current) return;
        window.speechSynthesis.cancel();
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        finish();
      }
    });
  }, [cleanSpeechText, clearTtsState, pickVoice, showVoiceToast, splitSpeech, startTtsPump, stopSpeak, stopTtsPump, ttsSupported, voiceLang]);

  const speakWithFallback = useCallback((text: string, onDone?: () => void) => {
    ttsRunRef.current += 1;
    ttsCancellingRef.current = true;
    if (ttsSupported) window.speechSynthesis.cancel();
    stopTtsPump();
    stopBackendSpeech();
    ttsCancellingRef.current = false;
    ttsActiveKeyRef.current = null;
    setTtsActiveKey(null);
    ttsTailRef.current = text;
    ttsQueueRef.current = [];
    ttsSourceDoneRef.current = false;
    ttsSpeakingRef.current = false;
    setTtsSpeaking(false);
    ttsEndRef.current = null;
    flushVoiceTts(true, onDone);
  }, [flushVoiceTts, stopTtsPump, ttsSupported]);

  const resetResponseSpeech = useCallback(() => {
    ttsRunRef.current += 1;
    ttsTailRef.current = '';
    ttsQueueRef.current = [];
    ttsSourceDoneRef.current = false;
    ttsSpeakingRef.current = false;
    setTtsSpeaking(false);
    ttsEndRef.current = null;
  }, []);

  const appendResponseToken = useCallback((token: string, active: boolean) => {
    if (!active) return;
    ttsTailRef.current += token;
    flushVoiceTts(false);
  }, [flushVoiceTts]);

  const finishResponseSpeech = useCallback((content: string, onDone: () => void) => {
    ttsEndRef.current = onDone;
    if (ttsTailRef.current || ttsQueueRef.current.length || ttsSpeakingRef.current) {
      flushVoiceTts(true, onDone);
    } else {
      speakWithFallback(content, onDone);
    }
  }, [flushVoiceTts, speakWithFallback]);

  const startVoiceCapture = useCallback((continuous: boolean, submit = true) => {
    if (streaming) {
      if (continuous && callModeRef.current) queueVoiceRestart(300);
      else if (!continuous && manualDictationRef.current) queueVoiceRestart(300, true);
      return;
    }
    if (!secureVoiceContext) {
      showVoiceToast(t('voiceNeedsSecureContext'), 'error');
      setCallMode(false);
      callModeRef.current = false;
      setListening(false);
      releaseWakeLock();
      return;
    }
    if (!voiceSupported) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      setCallMode(false);
      callModeRef.current = false;
      setListening(false);
      releaseWakeLock();
      return;
    }
    recognitionRunRef.current += 1;
    const runId = recognitionRunRef.current;
    recognitionRef.current?.abort?.();
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = voiceLang;
    rec.interimResults = true;
    rec.continuous = false;
    const baseText = inputRef.current?.value?.trim() || '';
    let finalText = '';
    let latestInterimText = '';
    let stopAfterError = false;
    let retryDelay: number | null = null;
    let speechSilenceTimer: number | null = null;
    const clearSpeechTimers = () => {
      if (speechSilenceTimer !== null) window.clearTimeout(speechSilenceTimer);
      speechSilenceTimer = null;
    };
    const stopAfterSpeechPause = () => {
      if (runId !== recognitionRunRef.current || stopAfterError) return;
      try { rec.stop(); } catch { /* onend handles browsers already stopping */ }
    };
    rec.onresult = (event: any) => {
      if (runId !== recognitionRunRef.current) return;
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += transcript;
        else interim += transcript;
      }
      latestInterimText = interim;
      setInput(`${baseText}${baseText && (finalText || interim) ? ' ' : ''}${finalText}${interim}`.trim());
      if (finalText.trim() || interim.trim()) {
        if (speechSilenceTimer !== null) window.clearTimeout(speechSilenceTimer);
        speechSilenceTimer = window.setTimeout(stopAfterSpeechPause, finalText.trim() ? 250 : 850);
      }
    };
    rec.onend = () => {
      if (runId !== recognitionRunRef.current) return;
      clearSpeechTimers();
      setListening(false);
      recognitionRef.current = null;
      if (stopAfterError) return;
      const text = (finalText || latestInterimText).trim();
      if (text && submit) {
        void sendTextRef.current(text, { viaVoice: true, continueCall: continuous });
      } else if (text && manualDictationRef.current) {
        inputRef.current?.focus();
        queueVoiceRestart(retryDelay ?? 500, true);
      } else if (text) {
        inputRef.current?.focus();
      } else if (continuous && callModeRef.current) {
        queueVoiceRestart(retryDelay ?? 500);
      } else if (manualDictationRef.current) {
        queueVoiceRestart(retryDelay ?? 500, true);
      } else {
        inputRef.current?.focus();
      }
    };
    rec.onerror = (event: any) => {
      if (runId !== recognitionRunRef.current) return;
      clearSpeechTimers();
      setListening(false);
      const error = String(event?.error || 'unknown');
      const permanent = ['not-allowed', 'service-not-allowed', 'audio-capture', 'language-not-supported'].includes(error);
      if (permanent) {
        stopAfterError = true;
        setCallMode(false);
        callModeRef.current = false;
        manualDictationRef.current = false;
        releaseWakeLock();
        const message = error === 'not-allowed'
          ? t('voiceMicPermissionDenied')
          : error === 'audio-capture'
          ? t('voiceNoMicrophone')
          : error === 'network' || error === 'service-not-allowed'
          ? t('voiceRecognitionUnsupported')
          : t('voiceRecognitionFailed');
        showVoiceToast(message, error === 'not-allowed' ? 'error' : 'warning');
        return;
      }
      retryDelay = error === 'no-speech' ? 700 : 1200;
    };
    rec.onstart = () => {
      if (runId !== recognitionRunRef.current) return;
      setListening(true);
    };
    recognitionRef.current = rec;
    audioManager.play(continuous ? 'call-enter' : 'stt-on');
    try {
      rec.start();
    } catch {
      recognitionRef.current = null;
      setListening(false);
      setCallMode(false);
      callModeRef.current = false;
      releaseWakeLock();
      showVoiceToast(t('voiceRecognitionFailed'), 'warning');
    }
  }, [inputRef, queueVoiceRestart, releaseWakeLock, sendTextRef, setInput, secureVoiceContext, showVoiceToast, streaming, t, voiceLang, voiceSupported]);

  useEffect(() => {
    startVoiceRef.current = voiceSupported ? startVoiceCapture : startBackendVoiceCapture;
  }, [startBackendVoiceCapture, startVoiceCapture, voiceSupported]);

  const cancelPendingCapture = useCallback(() => {
    manualDictationRef.current = false;
    backendVoiceRetryRef.current = 0;
    if (voiceRestartTimerRef.current !== null) {
      window.clearTimeout(voiceRestartTimerRef.current);
      voiceRestartTimerRef.current = null;
    }
    recognitionRunRef.current += 1;
    try { recognitionRef.current?.abort?.(); } catch { /* recognition may already be ending */ }
    recognitionRef.current = null;
    backendRecorderRunRef.current += 1;
    backendRecorderRef.current?.cancel();
    backendRecorderRef.current = null;
    backendTranscriptionAbortRef.current?.abort();
    backendTranscriptionAbortRef.current = null;
    setListening(false);
  }, []);

  const stopDictation = useCallback(() => {
    cancelPendingCapture();
    audioManager.play('stt-off');
  }, [cancelPendingCapture]);

  const stopVoice = useCallback(() => {
    cleanupVoiceResources();
    setCallMode(false);
    setListening(false);
    clearTtsState();
  }, [cleanupVoiceResources, clearTtsState]);

  const dictationStopRef = useRef<() => void>(() => {});
  dictationStopRef.current = stopDictation;

  const startCall = useCallback(() => {
    if (!secureVoiceContext) {
      showVoiceToast(t('voiceNeedsSecureContext'), 'error');
      return;
    }
    if (!voiceSupported && !detectBackendVoice()) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      return;
    }
    setCallMode(true);
    callModeRef.current = true;
    backendVoiceRetryRef.current = 0;
    requestWakeLock();
    if (voiceSupported) {
      unlockSpeech();
      startVoiceCapture(true);
    } else {
      void startBackendVoiceCapture(true);
    }
  }, [requestWakeLock, secureVoiceContext, showVoiceToast, startBackendVoiceCapture, startVoiceCapture, t, unlockSpeech, voiceSupported]);

  const startDictation = useCallback(() => {
    if (!secureVoiceContext) {
      showVoiceToast(t('voiceNeedsSecureContext'), 'error');
      return;
    }
    if (!voiceSupported && !detectBackendVoice()) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      return;
    }
    manualDictationRef.current = true;
    backendVoiceRetryRef.current = 0;
    if (voiceSupported) startVoiceCapture(false, false);
    else void startBackendVoiceCapture(false, false);
  }, [secureVoiceContext, showVoiceToast, startBackendVoiceCapture, startVoiceCapture, t, voiceSupported]);

  return {
    callMode,
    callModeRef,
    cancelPendingCapture,
    dictationStopRef,
    finishResponseSpeech,
    appendResponseToken,
    listening,
    listeningRef,
    queueVoiceRestart,
    resetResponseSpeech,
    secureVoiceContext,
    speak,
    speakWithFallback,
    startCall,
    startDictation,
    stopDictation,
    stopSpeak,
    stopVoice,
    ttsActiveKey,
    ttsSpeaking,
    ttsSupported,
    voiceSupported: voiceSupported || detectBackendVoice(),
  };
}
