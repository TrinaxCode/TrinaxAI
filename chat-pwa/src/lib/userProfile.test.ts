import { beforeEach, describe, expect, it, vi } from 'vitest';

import { rememberFromMessage } from './userProfile';

describe('user profile memory', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('does not fail the chat when browser storage rejects a memory write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Storage is unavailable', 'QuotaExceededError');
    });

    expect(rememberFromMessage('Recuerda que prefiero respuestas breves')).toBe(false);
  });
});
