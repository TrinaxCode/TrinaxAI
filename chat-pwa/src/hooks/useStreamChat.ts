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

const MAX_QUEUE = 500;

export function useStreamChat() {
  const [streaming, setStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [streamedMeta, setStreamedMeta] = useState<StreamMeta>({});
  const abortRef = useRef<AbortController | null>(null);
  const queueRef = useRef<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const accumRef = useRef('');
  const metaRef = useRef<StreamMeta>({});
  const discardAbortRef = useRef(false);
  const runIdRef = useRef(0);

  const killTimer = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }, []);

  // Cleanup on unmount: kill timer and abort any pending stream
  useEffect(() => {
    return () => {
      killTimer();
      abortRef.current?.abort();
    };
  }, [killTimer]);

  const startTimer = useCallback(() => {
    killTimer();
    timerRef.current = setInterval(() => {
      const q = queueRef.current;
      if (q.length === 0) return;
      accumRef.current += q.splice(0, 10).join('');
      setStreamedText(accumRef.current);
    }, 16);
  }, [killTimer]);

  const sendMessage = useCallback(
    async (messages: ChatMessage[], engine: ChatEngine, options?: SendOptions): Promise<SendResult> => {
      const runId = runIdRef.current + 1;
      runIdRef.current = runId;
      discardAbortRef.current = false;
      abortRef.current?.abort();
      killTimer();
      queueRef.current = [];
      accumRef.current = '';
      metaRef.current = {};
      setStreamedMeta({});

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      setStreaming(true);
      setStreamedText('');
      startTimer();

      const onMeta = (m: StreamMeta) => {
        if (runId !== runIdRef.current) return;
        metaRef.current = { ...metaRef.current, ...m };
        setStreamedMeta(metaRef.current);
      };

      try {
        const handleToken = (token: string) => {
          if (runId !== runIdRef.current) return;
          const q = queueRef.current;
          if (q.length < MAX_QUEUE) {
            for (const c of token) q.push(c);
          } else {
            // Queue saturated (background tab throttling): flush directly
            accumRef.current += token;
          }
          options?.onToken?.(token, accumRef.current + queueRef.current.join(''));
        };
        const streamOptions = { collections: options?.collections };
        const full = engine === 'rag'
          ? await streamRag(messages, handleToken, ctrl.signal, onMeta, streamOptions)
          : await streamOllama(messages, handleToken, ctrl.signal, onMeta, streamOptions);
        if (runId !== runIdRef.current) throw new Error('TRINAXAI_SILENT_ABORT');
        accumRef.current = full;
        queueRef.current = [];
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
          return { content: accumRef.current || '', meta: metaRef.current };
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
    [startTimer, killTimer],
  );

  const abort = useCallback((discard = false) => {
    discardAbortRef.current = discard;
    if (discard) runIdRef.current += 1;
    abortRef.current?.abort();
    killTimer();
    queueRef.current = [];
  }, [killTimer]);

  return { streaming, streamedText, streamedMeta, sendMessage, abort };
}
