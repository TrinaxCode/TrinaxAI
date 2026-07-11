import { describe, expect, it } from 'vitest';

import { streamFlushSize } from './useStreamChat';

describe('streamFlushSize', () => {
  it('keeps a smooth cadence for live tokens and drains large backlogs quickly', () => {
    expect(streamFlushSize(100)).toBe(32);
    expect(streamFlushSize(1500)).toBe(128);
    expect(streamFlushSize(5000)).toBe(512);
  });
});
