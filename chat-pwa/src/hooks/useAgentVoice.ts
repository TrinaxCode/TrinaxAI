import { useCallback, useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { detectBackendVoice, detectSpeechRecognition, transcribeAudio } from '../services/voice';
import { startAudioRecorder, type AudioRecorder } from '../utils/audioRecorder';
import type { Translate } from '../components/chat/types';

interface UseAgentVoiceOptions {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  lang: 'en' | 'es';
  setInput: Dispatch<SetStateAction<string>>;
  setImageError: Dispatch<SetStateAction<string>>;
  t: Translate;
}

interface AgentVoiceController {
  cancelDictation: () => void;
  dictationAvailable: boolean;
  listening: boolean;
  toggleDictation: () => void;
}

export function useAgentVoice({ inputRef, lang, setInput, setImageError, t }: UseAgentVoiceOptions): AgentVoiceController {
  const voiceLang = lang === 'en' ? 'en-US' : 'es-MX';
  const secureVoiceContext = typeof window !== 'undefined'
    && (window.isSecureContext || ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname));
  const voiceSupported = detectSpeechRecognition();
  const dictationAvailable = voiceSupported || detectBackendVoice();
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const recognitionRunRef = useRef(0);
  const recorderRef = useRef<AudioRecorder | null>(null);
  const recorderRunRef = useRef(0);
  const backendTranscriptionAbortRef = useRef<AbortController | null>(null);
  const manualDictationRef = useRef(false);
  const voiceRestartTimerRef = useRef<number | null>(null);
  const startDictationRef = useRef<() => void>(() => undefined);

  const cancelDictation = useCallback(() => {
    manualDictationRef.current = false;
    if (voiceRestartTimerRef.current !== null) {
      window.clearTimeout(voiceRestartTimerRef.current);
      voiceRestartTimerRef.current = null;
    }
    recognitionRunRef.current += 1;
    try { recognitionRef.current?.abort?.(); } catch { /* ignore */ }
    recognitionRef.current = null;
    recorderRunRef.current += 1;
    recorderRef.current?.cancel();
    recorderRef.current = null;
    backendTranscriptionAbortRef.current?.abort();
    backendTranscriptionAbortRef.current = null;
    setListening(false);
  }, []);

  const queueDictationRestart = useCallback((delay = 500) => {
    if (!manualDictationRef.current) return;
    if (voiceRestartTimerRef.current !== null) window.clearTimeout(voiceRestartTimerRef.current);
    voiceRestartTimerRef.current = window.setTimeout(() => {
      voiceRestartTimerRef.current = null;
      if (manualDictationRef.current) startDictationRef.current();
    }, delay);
  }, []);

  const startDictation = useCallback(async () => {
    recognitionRunRef.current += 1;
    try { recognitionRef.current?.abort?.(); } catch { /* recognition may already be ending */ }
    recognitionRef.current = null;
    recorderRunRef.current += 1;
    recorderRef.current?.cancel();
    recorderRef.current = null;
    backendTranscriptionAbortRef.current?.abort();
    backendTranscriptionAbortRef.current = null;
    if (voiceSupported) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      const runId = ++recognitionRunRef.current;
      recognition.lang = voiceLang;
      recognition.interimResults = true;
      recognition.continuous = manualDictationRef.current;
      const baseText = inputRef.current?.value?.trim() || '';
      let finalText = '';
      recognition.onresult = (event: any) => {
        if (runId !== recognitionRunRef.current) return;
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += transcript; else interim += transcript;
        }
        setInput(`${baseText}${baseText && (finalText || interim) ? ' ' : ''}${finalText}${interim}`.trim());
      };
      let stopAfterError = false;
      let retryDelay = 500;
      recognition.onerror = (event: any) => {
        if (runId !== recognitionRunRef.current) return;
        const error = String(event?.error || 'unknown');
        if (['not-allowed', 'service-not-allowed', 'audio-capture', 'language-not-supported'].includes(error)) {
          stopAfterError = true;
          manualDictationRef.current = false;
          setListening(false);
          setImageError(error === 'not-allowed'
            ? t('voiceMicPermissionDenied')
            : error === 'audio-capture'
              ? t('voiceNoMicrophone')
              : error === 'service-not-allowed' || error === 'language-not-supported'
                ? t('voiceRecognitionUnsupported')
                : t('voiceRecognitionFailed'));
          return;
        }
        retryDelay = error === 'no-speech' ? 700 : 1200;
      };
      recognition.onend = () => {
        if (runId !== recognitionRunRef.current) return;
        setListening(false);
        recognitionRef.current = null;
        if (!stopAfterError && manualDictationRef.current) {
          inputRef.current?.focus();
          queueDictationRestart(retryDelay);
        }
      };
      recognition.onstart = () => { if (runId === recognitionRunRef.current) setListening(true); };
      recognitionRef.current = recognition;
      try { recognition.start(); } catch {
        recognitionRef.current = null;
        setListening(false);
        if (manualDictationRef.current) queueDictationRestart(1200);
      }
      return;
    }
    // Backend fallback: record until silence, then transcribe.
    if (!detectBackendVoice()) return;
    const runId = ++recorderRunRef.current;
    try {
      const recorder = await startAudioRecorder({
        onStart: () => { if (runId === recorderRunRef.current) setListening(true); },
        onSilence: async (blob) => {
          if (runId !== recorderRunRef.current || !manualDictationRef.current) return;
          recorderRef.current = null;
          setListening(false);
          const transcriptionController = new AbortController();
          backendTranscriptionAbortRef.current?.abort();
          backendTranscriptionAbortRef.current = transcriptionController;
          try {
            const text = await transcribeAudio(blob, voiceLang, transcriptionController.signal);
            if (runId !== recorderRunRef.current || !manualDictationRef.current) return;
            if (text.trim()) setInput((previous) => `${previous ? `${previous} ` : ''}${text.trim()}`);
            inputRef.current?.focus();
            queueDictationRestart();
          } catch {
            if (!transcriptionController.signal.aborted && runId === recorderRunRef.current && manualDictationRef.current) {
              setImageError(t('voiceRecognitionFailed'));
              queueDictationRestart(1200);
            }
          } finally {
            if (backendTranscriptionAbortRef.current === transcriptionController) backendTranscriptionAbortRef.current = null;
          }
        },
        onError: (error) => {
          if (runId !== recorderRunRef.current) return;
          recorderRef.current = null;
          setListening(false);
          const permissionDenied = ['NotAllowedError', 'SecurityError'].includes(error.name);
          if (permissionDenied) {
            manualDictationRef.current = false;
            setImageError(t('voiceMicPermissionDenied'));
          } else if (manualDictationRef.current) queueDictationRestart(1200);
        },
      }, 2200);
      if (runId !== recorderRunRef.current || !manualDictationRef.current) {
        recorder.cancel();
        return;
      }
      recorderRef.current = recorder;
    } catch (error: unknown) {
      if (runId !== recorderRunRef.current || !manualDictationRef.current) return;
      const permissionDenied = error instanceof Error && ['NotAllowedError', 'SecurityError'].includes(error.name);
      setListening(false);
      setImageError(permissionDenied ? t('voiceMicPermissionDenied') : t('voiceRecognitionFailed'));
      if (permissionDenied) manualDictationRef.current = false;
      else queueDictationRestart(1200);
    }
  }, [inputRef, queueDictationRestart, setImageError, setInput, t, voiceLang, voiceSupported]);

  useEffect(() => {
    startDictationRef.current = () => { void startDictation(); };
  }, [startDictation]);

  useEffect(() => () => {
    manualDictationRef.current = false;
    if (voiceRestartTimerRef.current !== null) window.clearTimeout(voiceRestartTimerRef.current);
    try { recognitionRef.current?.abort?.(); } catch { /* ignore */ }
    recognitionRunRef.current += 1;
    recorderRunRef.current += 1;
    recorderRef.current?.cancel();
    recorderRef.current = null;
    backendTranscriptionAbortRef.current?.abort();
    backendTranscriptionAbortRef.current = null;
  }, []);

  const toggleDictation = useCallback(() => {
    if (listening) cancelDictation();
    else {
      if (!secureVoiceContext) {
        setImageError(t('voiceNeedsSecureContext'));
        return;
      }
      manualDictationRef.current = true;
      void startDictation();
    }
  }, [cancelDictation, listening, secureVoiceContext, setImageError, startDictation, t]);

  return { cancelDictation, dictationAvailable, listening, toggleDictation };
}
