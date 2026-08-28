import { useRef, useCallback, useState, useEffect } from 'react';
import type { ChatMessage, ChatEngine, StreamMeta } from '../lib/api';
import { streamOllama, streamRag } from '../lib/api';
import { useI18n } from '../i18n/I18nContext';

export interface SendResult {
  content: string;
  meta: StreamMeta;
  thinking?: string;
  thinkingDurationMs?: number;
}

export interface SendOptions {
  onToken?: (token: string, fullText: string) => void;
  collections?: string[];
  mode?: 'auto' | 'knowledge' | 'model';
  temporary?: boolean;
}

export interface ExternalStream {
  onToken: (token: string) => void;
  finish: (fullText: string) => Promise<string>;
  cancel: () => void;
}

const MAX_BUFFER_CHARS = 8192;
export const FIRST_TOKEN_TIMEOUT_MS = 15 * 60_000;
export const VISION_FIRST_TOKEN_TIMEOUT_MS = 20 * 60_000;

export function firstTokenTimeoutMs(messages: ChatMessage[]): number {
  return messages[messages.length - 1]?.image
    ? VISION_FIRST_TOKEN_TIMEOUT_MS
    : FIRST_TOKEN_TIMEOUT_MS;
}

export function streamFlushSize(pendingChars: number): number {
  if (pendingChars > 4096) return 512;
  if (pendingChars > 1024) return 128;
  return 32;
}

export function useStreamChat() {
  const { t } = useI18n();
  const [streaming, setStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [streamedThinking, setStreamedThinking] = useState('');
  const [streamedMeta, setStreamedMeta] = useState<StreamMeta>({});
  const abortRef = useRef<AbortController | null>(null);
  const queueRef = useRef('');
  const frameRef = useRef<number | null>(null);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const accumRef = useRef('');
  const metaRef = useRef<StreamMeta>({});
  const discardAbortRef = useRef(false);
  const runIdRef = useRef(0);
  const wasAbortedRef = useRef(false);
  const thinkingRef = useRef('');
  const thinkingStartedAtRef = useRef<number | null>(null);
  const thinkingDurationRef = useRef<number | undefined>(undefined);

  const killTimer = useCallback(() => {
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
  }, []);

  // Cleanup on unmount: kill timer and abort any pending stream
  useEffect(() => {
    return () => {
      killTimer();
      abortRef.current?.abort();
    };
  }, [killTimer]);

  const flushQueue = useCallback(() => {
    frameRef.current = null;
    fallbackTimerRef.current = null;
    const pending = queueRef.current;
    if (!pending) return;
    // Keep the typewriter effect even when an endpoint delivers a complete
    // response in one network chunk (RAG commonly does this).
    const visible = pending.slice(0, streamFlushSize(pending.length));
    queueRef.current = pending.slice(visible.length);
    accumRef.current += visible;
    setStreamedText(accumRef.current);
    if (queueRef.current) {
      fallbackTimerRef.current = setTimeout(flushQueue, 18);
    }
  }, []);

  const scheduleFlush = useCallback(() => {
    if (frameRef.current !== null || fallbackTimerRef.current) return;
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      frameRef.current = window.requestAnimationFrame(flushQueue);
      return;
    }
    fallbackTimerRef.current = setTimeout(flushQueue, 16);
  }, [flushQueue]);

  const sendMessage = useCallback(
    async (messages: ChatMessage[], engine: ChatEngine, options?: SendOptions): Promise<SendResult> => {
      const runId = runIdRef.current + 1;
      runIdRef.current = runId;
      discardAbortRef.current = false;
      abortRef.current?.abort();
      killTimer();
      queueRef.current = '';
      accumRef.current = '';
      metaRef.current = {};
      thinkingRef.current = '';
      thinkingStartedAtRef.current = null;
      thinkingDurationRef.current = undefined;
      setStreamedMeta({});
      setStreamedThinking('');

      const ctrl = new AbortController();
      abortRef.current = ctrl;
      let firstTokenTimer: ReturnType<typeof setTimeout> | null = null;
      let firstTokenTimedOut = false;

      wasAbortedRef.current = false;
      setStreaming(true);
      setStreamedText('');

      const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());
      const handleThinking = (token: string) => {
        if (runId !== runIdRef.current || !token) return;
        // Duration is provider-observable thinking latency: first thinking delta to first final token, or stream end.
        thinkingStartedAtRef.current ??= now();
        thinkingRef.current += token;
        setStreamedThinking(thinkingRef.current);
      };
      const handleThinkingDuration = (durationMs: number) => {
        if (!Number.isFinite(durationMs) || durationMs < 0) return;
        thinkingDurationRef.current = durationMs;
        metaRef.current = { ...metaRef.current, thinkingDurationMs: durationMs };
        setStreamedMeta(metaRef.current);
      };

      const onMeta = (m: StreamMeta) => {
        if (runId !== runIdRef.current) return;
        metaRef.current = { ...metaRef.current, ...m };
        setStreamedMeta(metaRef.current);
      };

      try {
        firstTokenTimer = setTimeout(() => {
          firstTokenTimedOut = true;
          ctrl.abort();
        }, firstTokenTimeoutMs(messages));
        const handleToken = (token: string) => {
          if (runId !== runIdRef.current) return;
          if (firstTokenTimer) { clearTimeout(firstTokenTimer); firstTokenTimer = null; }
          if (thinkingStartedAtRef.current !== null && thinkingDurationRef.current === undefined) {
            thinkingDurationRef.current = Math.max(0, now() - thinkingStartedAtRef.current);
          }
          queueRef.current += token;
          if (queueRef.current.length >= MAX_BUFFER_CHARS) {
            flushQueue();
          } else {
            scheduleFlush();
          }
          options?.onToken?.(token, accumRef.current + queueRef.current);
        };
        const streamOptions = {
          collections: options?.collections,
          mode: options?.mode,
          temporary: options?.temporary,
          onThinking: handleThinking,
          onThinkingDuration: handleThinkingDuration,
        };
        const full = engine === 'rag'
          ? await streamRag(messages, handleToken, ctrl.signal, onMeta, streamOptions)
          : await streamOllama(messages, handleToken, ctrl.signal, onMeta, streamOptions);
        if (ctrl.signal.aborted) throw new DOMException('The response was cancelled.', 'AbortError');
        if (runId !== runIdRef.current) throw new Error('TRINAXAI_SILENT_ABORT');
        // Do not replace the animated text with the complete answer before
        // the queued characters have been painted.
        scheduleFlush();
        await new Promise<void>((resolve) => {
          const waitForAnimation = () => {
            if (!queueRef.current && frameRef.current === null && !fallbackTimerRef.current) {
              resolve();
              return;
            }
            window.setTimeout(waitForAnimation, 16);
          };
          waitForAnimation();
        });
        accumRef.current = full;
        setStreamedText(full);
        if (thinkingStartedAtRef.current !== null && thinkingDurationRef.current === undefined) {
          thinkingDurationRef.current = Math.max(0, now() - thinkingStartedAtRef.current);
        }
        setStreamedThinking(thinkingRef.current);
        killTimer();
        return {
          content: full,
          meta: metaRef.current,
          thinking: thinkingRef.current || undefined,
          thinkingDurationMs: thinkingDurationRef.current,
        };
      } catch (err: unknown) {
        killTimer();
        if (runId !== runIdRef.current) {
          throw new Error('TRINAXAI_SILENT_ABORT');
        }
        if (err instanceof DOMException && err.name === 'AbortError') {
          if (firstTokenTimedOut) throw new Error(t('responseTimeoutMessage'));
          if (discardAbortRef.current) {
            throw new Error('TRINAXAI_SILENT_ABORT');
          }
          if (thinkingStartedAtRef.current !== null && thinkingDurationRef.current === undefined) {
            thinkingDurationRef.current = Math.max(0, now() - thinkingStartedAtRef.current);
          }
          metaRef.current = {
            ...metaRef.current,
            finishReason: 'cancelled',
            completionStatus: 'cancelled',
            canContinue: false,
          };
          return {
            content: accumRef.current + queueRef.current,
            meta: metaRef.current,
            thinking: thinkingRef.current || undefined,
            thinkingDurationMs: thinkingDurationRef.current,
          };
        }
        throw err;
      } finally {
        if (firstTokenTimer) clearTimeout(firstTokenTimer);
        if (runId === runIdRef.current) {
          killTimer();
          setStreaming(false);
          abortRef.current = null;
        }
      }
    },
    [flushQueue, scheduleFlush, killTimer],
  );

  /** Reveal a complete non-streaming response with the same buffered cadence
   * used by Ollama/RAG token streams (web search and deep research use this). */
  const revealText = useCallback(async (text: string): Promise<string> => {
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    discardAbortRef.current = false;
    abortRef.current?.abort();
    abortRef.current = null;
    killTimer();
    queueRef.current = text;
    accumRef.current = '';
    metaRef.current = {};
    wasAbortedRef.current = false;
    thinkingRef.current = '';
    thinkingStartedAtRef.current = null;
    thinkingDurationRef.current = undefined;
    setStreamedMeta({});
    setStreamedThinking('');
    setStreamedText('');
    setStreaming(true);
    scheduleFlush();

    try {
      await new Promise<void>((resolve) => {
        const waitForAnimation = () => {
          if (runId !== runIdRef.current || (!queueRef.current && frameRef.current === null && !fallbackTimerRef.current)) {
            resolve();
            return;
          }
          window.setTimeout(waitForAnimation, 16);
        };
        waitForAnimation();
      });
      if (runId !== runIdRef.current) throw new Error('TRINAXAI_SILENT_ABORT');
      const revealed = wasAbortedRef.current ? accumRef.current : text;
      accumRef.current = revealed;
      setStreamedText(revealed);
      return revealed;
    } finally {
      if (runId === runIdRef.current) {
        killTimer();
        setStreaming(false);
      }
    }
  }, [killTimer, scheduleFlush]);

  const startExternalStream = useCallback((): ExternalStream => {
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    discardAbortRef.current = false;
    abortRef.current?.abort();
    killTimer();
    queueRef.current = '';
    accumRef.current = '';
    wasAbortedRef.current = false;
    thinkingRef.current = '';
    thinkingStartedAtRef.current = null;
    thinkingDurationRef.current = undefined;
    setStreamedMeta({});
    setStreamedThinking('');
    setStreamedText('');
    setStreaming(true);

    const onToken = (token: string) => {
      if (runId !== runIdRef.current || wasAbortedRef.current) return;
      queueRef.current += token;
      if (queueRef.current.length >= MAX_BUFFER_CHARS) flushQueue();
      else scheduleFlush();
    };
    const finish = async (fullText: string): Promise<string> => {
      if (runId !== runIdRef.current) throw new Error('TRINAXAI_SILENT_ABORT');
      scheduleFlush();
      await new Promise<void>((resolve) => {
        const waitForAnimation = () => {
          if (!queueRef.current && frameRef.current === null && !fallbackTimerRef.current) {
            resolve();
            return;
          }
          window.setTimeout(waitForAnimation, 16);
        };
        waitForAnimation();
      });
      if (runId !== runIdRef.current) throw new Error('TRINAXAI_SILENT_ABORT');
      const revealed = wasAbortedRef.current ? accumRef.current : fullText;
      accumRef.current = revealed;
      setStreamedText(revealed);
      setStreaming(false);
      killTimer();
      return revealed;
    };
    const cancel = () => {
      if (runId !== runIdRef.current) return;
      wasAbortedRef.current = true;
      runIdRef.current += 1;
      killTimer();
      queueRef.current = '';
      setStreaming(false);
    };
    return { onToken, finish, cancel };
  }, [flushQueue, killTimer, scheduleFlush]);

  const abort = useCallback((discard = false) => {
    wasAbortedRef.current = true;
    discardAbortRef.current = discard;
    if (discard) runIdRef.current += 1;
    abortRef.current?.abort();
    killTimer();
    if (discard) {
      queueRef.current = '';
    } else if (queueRef.current) {
      accumRef.current += queueRef.current;
      queueRef.current = '';
      setStreamedText(accumRef.current);
    }
  }, [killTimer]);

  const wasAborted = useCallback(() => wasAbortedRef.current, []);

  return { streaming, streamedText, streamedThinking, streamedMeta, sendMessage, revealText, startExternalStream, abort, wasAborted };
}
