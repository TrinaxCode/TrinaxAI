import { useRef, useCallback, useState, useEffect } from 'react';
import type { ChatMessage, ChatEngine, StreamMeta } from '../lib/api';
import { streamOllama, streamRag } from '../lib/api';

export interface SendResult {
  content: string;
  meta: StreamMeta;
}

export interface SendOptions {
  onToken?: (token: string, fullText: string) => void;
  collections?: string[];
}

const MAX_BUFFER_CHARS = 8192;

export function streamFlushSize(pendingChars: number): number {
  if (pendingChars > 4096) return 512;
  if (pendingChars > 1024) return 128;
  return 32;
}

export function useStreamChat() {
  const [streaming, setStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
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
      setStreamedMeta({});

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      wasAbortedRef.current = false;
      setStreaming(true);
      setStreamedText('');

      const onMeta = (m: StreamMeta) => {
        if (runId !== runIdRef.current) return;
        metaRef.current = { ...metaRef.current, ...m };
        setStreamedMeta(metaRef.current);
      };

      try {
        const handleToken = (token: string) => {
          if (runId !== runIdRef.current) return;
          queueRef.current += token;
          if (queueRef.current.length >= MAX_BUFFER_CHARS) {
            flushQueue();
          } else {
            scheduleFlush();
          }
          options?.onToken?.(token, accumRef.current + queueRef.current);
        };
        const streamOptions = { collections: options?.collections };
        const full = engine === 'rag'
          ? await streamRag(messages, handleToken, ctrl.signal, onMeta, streamOptions)
          : await streamOllama(messages, handleToken, ctrl.signal, onMeta, streamOptions);
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
        killTimer();
        return { content: full, meta: metaRef.current };
      } catch (err: unknown) {
        killTimer();
        if (runId !== runIdRef.current) {
          throw new Error('TRINAXAI_SILENT_ABORT');
        }
        if (err instanceof DOMException && err.name === 'AbortError') {
          if (discardAbortRef.current) {
            throw new Error('TRINAXAI_SILENT_ABORT');
          }
          return { content: accumRef.current + queueRef.current, meta: metaRef.current };
        }
        throw err;
      } finally {
        if (runId === runIdRef.current) {
          killTimer();
          setStreaming(false);
          abortRef.current = null;
        }
      }
    },
    [flushQueue, scheduleFlush, killTimer],
  );

  const abort = useCallback((discard = false) => {
    wasAbortedRef.current = true;
    discardAbortRef.current = discard;
    if (discard) runIdRef.current += 1;
    abortRef.current?.abort();
    killTimer();
    queueRef.current = '';
  }, [killTimer]);

  const wasAborted = useCallback(() => wasAbortedRef.current, []);

  return { streaming, streamedText, streamedMeta, sendMessage, abort, wasAborted };
}
