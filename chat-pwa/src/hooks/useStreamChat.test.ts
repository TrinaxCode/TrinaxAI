import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { streamFlushSize, useStreamChat } from './useStreamChat';

describe('streamFlushSize', () => {
  it('keeps a smooth cadence for live tokens and drains large backlogs quickly', () => {
    expect(streamFlushSize(100)).toBe(32);
    expect(streamFlushSize(1500)).toBe(128);
    expect(streamFlushSize(5000)).toBe(512);
  });
});

describe('non-streaming response reveal', () => {
  it('buffers a complete research answer instead of displaying it at once', async () => {
    const answer = 'Respuesta investigada '.repeat(18).trim();
    const { result } = renderHook(() => useStreamChat());
    let reveal!: Promise<string>;

    act(() => {
      reveal = result.current.revealText(answer);
    });

    expect(result.current.streaming).toBe(true);
    expect(result.current.streamedText).not.toBe(answer);

    await act(async () => {
      await expect(reveal).resolves.toBe(answer);
    });
    expect(result.current.streamedText).toBe(answer);
    expect(result.current.streaming).toBe(false);
  });
});
