import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useChatScroll } from './useChatScroll';

function scrollBox({ height = 1000, top = 0, viewport = 300 } = {}) {
  const element = document.createElement('div');
  Object.defineProperties(element, {
    scrollHeight: { configurable: true, value: height },
    clientHeight: { configurable: true, value: viewport },
    scrollTo: {
      configurable: true,
      value: vi.fn(({ top: nextTop }: ScrollToOptions) => {
        element.scrollTop = nextTop ?? element.scrollTop;
      }),
    },
  });
  element.scrollTop = top;
  return element;
}

describe('useChatScroll', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => (
      window.setTimeout(() => callback(performance.now()), 0)
    ));
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => clearTimeout(id));
  });

  afterEach(() => vi.useRealTimers());

  it('shows the jump button only after the user stays far from the bottom', () => {
    const { result } = renderHook(() => useChatScroll({ messageCount: 4, streamedText: '', streaming: false }));
    const element = scrollBox();
    result.current.messagesRef.current = element;

    act(() => result.current.updateScrollState());
    expect(result.current.showScrollButton).toBe(false);
    act(() => vi.advanceTimersByTime(250));
    expect(result.current.showScrollButton).toBe(true);

    element.scrollTop = 700;
    act(() => result.current.updateScrollState());
    expect(result.current.showScrollButton).toBe(false);
  });

  it('scrolls to the exact bottom and suppresses the button while settling', () => {
    const { result } = renderHook(() => useChatScroll({ messageCount: 1, streamedText: '', streaming: false }));
    const element = scrollBox({ height: 900, viewport: 250 });
    result.current.messagesRef.current = element;

    act(() => result.current.scrollToBottom('auto'));

    expect(element.scrollTo).toHaveBeenCalledWith({ top: 650, behavior: 'auto' });
    expect(result.current.showScrollButton).toBe(false);
    act(() => vi.advanceTimersByTime(140));
    expect(result.current.showScrollButton).toBe(false);
  });

  it('keeps following new streamed text when streaming starts at the bottom', () => {
    const { result, rerender } = renderHook(
      ({ text, streaming }) => useChatScroll({ messageCount: 1, streamedText: text, streaming }),
      { initialProps: { text: '', streaming: false } },
    );
    const element = scrollBox({ height: 500, top: 200, viewport: 300 });
    result.current.messagesRef.current = element;

    rerender({ text: '', streaming: true });
    rerender({ text: 'next token', streaming: true });
    act(() => vi.advanceTimersByTime(0));

    expect(element.scrollTo).toHaveBeenCalledWith({ top: 200, behavior: 'auto' });
  });
});
