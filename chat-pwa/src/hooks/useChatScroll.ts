import { useCallback, useEffect, useRef, useState } from 'react';

interface UseChatScrollOptions {
  messageCount: number;
  streamedText: string;
  streaming: boolean;
}

export function useChatScroll({ messageCount, streamedText, streaming }: UseChatScrollOptions) {
  const messagesRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const showScrollButtonRef = useRef(false);
  const autoScrollUntilRef = useRef(0);
  const followStreamingRef = useRef(false);
  const programmaticScrollTopRef = useRef<number | null>(null);
  const scrollButtonTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAtBottom = useCallback((element: HTMLDivElement) => (
    element.scrollHeight - element.scrollTop - element.clientHeight <= 32
  ), []);

  const updateScrollState = useCallback(() => {
    const element = messagesRef.current;
    if (!element) return;
    const expectedScrollTop = programmaticScrollTopRef.current;
    const movedByCode = expectedScrollTop !== null && Math.abs(element.scrollTop - expectedScrollTop) <= 2;
    if (isAtBottom(element)) {
      followStreamingRef.current = streaming;
    } else if (streaming && !movedByCode) {
      followStreamingRef.current = false;
    }
    const scrollable = element.scrollHeight > element.clientHeight + 16;
    if (Date.now() < autoScrollUntilRef.current) {
      if (showScrollButtonRef.current) {
        showScrollButtonRef.current = false;
        setShowScrollButton(false);
      }
      return;
    }
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    const shouldShow = scrollable && distance > 200;
    if (!shouldShow && scrollButtonTimerRef.current) {
      clearTimeout(scrollButtonTimerRef.current);
      scrollButtonTimerRef.current = null;
    }
    if (!shouldShow && showScrollButtonRef.current) {
      showScrollButtonRef.current = false;
      setShowScrollButton(false);
      return;
    }
    if (shouldShow && !showScrollButtonRef.current && !scrollButtonTimerRef.current) {
      scrollButtonTimerRef.current = setTimeout(() => {
        scrollButtonTimerRef.current = null;
        const current = messagesRef.current;
        if (!current || current.scrollHeight - current.scrollTop - current.clientHeight <= 200) return;
        showScrollButtonRef.current = true;
        setShowScrollButton(true);
      }, 250);
    }
  }, [isAtBottom, streaming]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth', followStream = false) => {
    const element = messagesRef.current;
    if (!element) return;
    if (followStream) followStreamingRef.current = true;
    autoScrollUntilRef.current = Date.now() + (behavior === 'smooth' ? 750 : 120);
    const target = Math.max(0, element.scrollHeight - element.clientHeight);
    programmaticScrollTopRef.current = target;
    element.scrollTo({ top: target, behavior });
    showScrollButtonRef.current = false;
    setShowScrollButton(false);
    if (scrollButtonTimerRef.current) {
      clearTimeout(scrollButtonTimerRef.current);
      scrollButtonTimerRef.current = null;
    }
    if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
    settleTimerRef.current = window.setTimeout(() => {
      settleTimerRef.current = null;
      autoScrollUntilRef.current = 0;
      updateScrollState();
    }, behavior === 'smooth' ? 780 : 140);
  }, [updateScrollState]);

  useEffect(() => {
    const frame = requestAnimationFrame(updateScrollState);
    return () => cancelAnimationFrame(frame);
  }, [messageCount, streamedText, streaming, updateScrollState]);

  useEffect(() => {
    const element = messagesRef.current;
    if (!streaming) {
      followStreamingRef.current = false;
      return;
    }
    followStreamingRef.current = followStreamingRef.current || Boolean(element && isAtBottom(element));
  }, [streaming, isAtBottom]);

  useEffect(() => {
    if (!streaming || !followStreamingRef.current) return;
    const frame = requestAnimationFrame(() => scrollToBottom('auto'));
    return () => cancelAnimationFrame(frame);
  }, [streamedText, messageCount, streaming, scrollToBottom]);

  useEffect(() => () => {
    if (scrollButtonTimerRef.current) clearTimeout(scrollButtonTimerRef.current);
    if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
  }, []);

  return { messagesRef, showScrollButton, updateScrollState, scrollToBottom };
}
