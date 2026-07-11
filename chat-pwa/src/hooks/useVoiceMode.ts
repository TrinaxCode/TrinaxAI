/* useVoiceMode: robust call-mode lifecycle with Web Speech + backend fallback.
   Hook del modo llamada con Web Speech y fallback a backend de audio. */

import {
  useCallback, useEffect, useRef, useState,
} from 'react';
import {
  detectBackendVoice,
  detectSpeechRecognition,
  detectSpeechSynthesis,
  speakBackend,
  transcribeAudio,
} from '../services/voice';
import { startAudioRecorder } from '../utils/audioRecorder';

export interface VoiceModeOptions {
  lang: 'en' | 'es';
  onText: (text: string) => void;
  onError?: (message: string) => void;
}

export interface VoiceModeState {
  callMode: boolean;
  isListening: boolean;
  isSpeaking: boolean;
  start: () => void;
  stop: () => void;
  toggle: () => void;
  speakWithBackend: (text: string, onDone?: () => void) => void;
}

const MAX_RETRIES = 3;

export function useVoiceMode({ lang, onText, onError }: VoiceModeOptions): VoiceModeState {
  const [callMode, setCallMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const callModeRef = useRef(callMode);
  const retryCountRef = useRef(0);
  const cancelRef = useRef<(() => void) | null>(null);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => { callModeRef.current = callMode; }, [callMode]);

  const releaseWakeLock = useCallback(() => {
    wakeLockRef.current?.release().catch(() => {});
    wakeLockRef.current = null;
  }, []);

  const requestWakeLock = useCallback(async () => {
    try {
      wakeLockRef.current = await (navigator as any).wakeLock?.request?.('screen');
    } catch {
      // iOS Safari fallback: silent loop is handled by the component if needed.
    }
  }, []);

  const stopTts = useCallback(() => {
    if (activeAudioRef.current) {
      const audio = activeAudioRef.current;
      const source = audio.src;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      if (source.startsWith('blob:')) URL.revokeObjectURL(source);
      activeAudioRef.current = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  const stopListening = useCallback(() => {
    cancelRef.current?.();
    cancelRef.current = null;
    setIsListening(false);
  }, []);

  const stopAll = useCallback(() => {
    setCallMode(false);
    callModeRef.current = false;
    stopListening();
    stopTts();
    releaseWakeLock();
    retryCountRef.current = 0;
  }, [stopListening, stopTts, releaseWakeLock]);

  const handleError = useCallback((message: string) => {
    onError?.(message);
    stopAll();
  }, [onError, stopAll]);

  const restartDelay = useCallback((ms: number, fn: () => void) => {
    if (!callModeRef.current) return;
    window.setTimeout(fn, ms);
  }, []);

  const restartListening = useCallback(() => {
    if (!callModeRef.current) return;
    if (retryCountRef.current >= MAX_RETRIES) {
      handleError('voiceTooManyRetries');
      return;
    }
    retryCountRef.current = 0;
    startBackendListening();
  }, [handleError]);

  const startBackendListening = useCallback(async () => {
    if (!callModeRef.current) return;
    if (!detectBackendVoice()) {
      handleError('voiceRecognitionUnsupported');
      return;
    }
    setIsListening(true);
    try {
      const recorder = await startAudioRecorder({
        onSilence: async (blob) => {
          if (!callModeRef.current) return;
          setIsListening(false);
          try {
            const text = await transcribeAudio(blob, lang === 'en' ? 'en-US' : 'es-ES');
            retryCountRef.current = 0;
            if (text.trim()) onText(text.trim());
            else if (callModeRef.current) restartDelay(500, startBackendListening);
          } catch {
            retryCountRef.current += 1;
            if (retryCountRef.current >= MAX_RETRIES) {
              handleError('voiceRecognitionFailed');
            } else if (callModeRef.current) {
              restartDelay(1000, startBackendListening);
            }
          }
        },
        onError: () => {
          setIsListening(false);
          handleError('voiceRecognitionFailed');
        },
      }, 1500);
      cancelRef.current = () => recorder.stop();
    } catch {
      setIsListening(false);
      handleError('voiceMicPermissionDenied');
    }
  }, [lang, onText, handleError, restartDelay]);

  const startWebSpeech = useCallback(() => {
    if (!callModeRef.current) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      startBackendListening();
      return;
    }
    const rec = new SR();
    rec.lang = lang === 'en' ? 'en-US' : 'es-ES';
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = '';

    rec.onresult = (e: any) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const tr = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += tr;
        else interim += tr;
      }
      // We ignore interim text for the call-mode flow; final text triggers the send.
      void interim;
    };

    rec.onend = () => {
      setIsListening(false);
      cancelRef.current = null;
      if (!callModeRef.current) return;
      const text = finalText.trim();
      if (text) {
        retryCountRef.current = 0;
        onText(text);
      } else {
        restartDelay(500, startWebSpeech);
      }
    };

    rec.onerror = (event: any) => {
      setIsListening(false);
      cancelRef.current = null;
      const error = String(event?.error || 'unknown');
      const permanent = ['not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'language-not-supported'];
      if (permanent.includes(error)) {
        handleError(error === 'not-allowed' ? 'voiceMicPermissionDenied' : 'voiceRecognitionFailed');
        return;
      }
      if (error === 'no-speech' && callModeRef.current) {
        restartDelay(900, startWebSpeech);
      }
    };

    try {
      rec.start();
      setIsListening(true);
      cancelRef.current = () => rec.abort();
    } catch {
      handleError('voiceRecognitionFailed');
    }
  }, [lang, onText, handleError, startBackendListening, restartDelay]);

  const start = useCallback(() => {
    if (callModeRef.current) return;
    setCallMode(true);
    callModeRef.current = true;
    retryCountRef.current = 0;
    requestWakeLock();
    if (detectSpeechRecognition()) startWebSpeech();
    else startBackendListening();
  }, [requestWakeLock, startWebSpeech, startBackendListening]);

  const stop = useCallback(() => {
    stopAll();
  }, [stopAll]);

  const toggle = useCallback(() => {
    if (callModeRef.current) stop();
    else start();
  }, [start, stop]);

  const speakWithBackend = useCallback((text: string, onDone?: () => void) => {
    setIsSpeaking(true);
    speakBackend({
      text,
      lang: lang === 'en' ? 'en-US' : 'es-ES',
      onEnded: () => {
        setIsSpeaking(false);
        onDone?.();
      },
      onError: () => {
        setIsSpeaking(false);
        onDone?.();
      },
    }).then((audio) => {
      activeAudioRef.current = audio;
    }).catch(() => {
      setIsSpeaking(false);
      onDone?.();
    });
  }, [lang]);

  // Pause TTS when the page goes to background to avoid Chrome audio bugs.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden && activeAudioRef.current) {
        activeAudioRef.current.pause();
      } else if (!document.hidden && activeAudioRef.current) {
        activeAudioRef.current.play().catch(() => {});
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  // Release wake lock when the user leaves the tab.
  useEffect(() => {
    const onBlur = () => releaseWakeLock();
    window.addEventListener('blur', onBlur);
    return () => window.removeEventListener('blur', onBlur);
  }, [releaseWakeLock]);

  return {
    callMode,
    isListening,
    isSpeaking,
    start,
    stop,
    toggle,
    // Expose speakWithBackend for components that need backend TTS fallback.
    speakWithBackend,
  };
}
