import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useChatHistory } from '../hooks/useChatHistory';
import { wipeRevokedDeviceData } from './deviceWipe';

describe('revoked device wipe', () => {
  it('erases local and session state plus browser caches', async () => {
    localStorage.setItem('tc-chat-sessions', '[{"private":true}]');
    localStorage.setItem('tc-agent-sessions', '[{"private":true}]');
    sessionStorage.setItem('trinaxai-device-token', 'revoked');
    const cacheDelete = vi.fn().mockResolvedValue(true);
    vi.stubGlobal('caches', { keys: vi.fn().mockResolvedValue(['trinaxai-cache']), delete: cacheDelete });

    await wipeRevokedDeviceData();

    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(cacheDelete).toHaveBeenCalledWith('trinaxai-cache');
    vi.unstubAllGlobals();
  });

  it('empties mounted chat state and cancels delayed history rewrites', async () => {
    localStorage.setItem('tc-chat-sessions', JSON.stringify([{
      id: 'private-chat', title: 'Privado', engine: 'ollama', messages: [{ role: 'user', content: 'secreto' }], createdAt: 1, updatedAt: 1,
    }]));
    const { result } = renderHook(() => useChatHistory());
    expect(result.current.sessions).toHaveLength(1);

    await act(() => wipeRevokedDeviceData());
    await new Promise((resolve) => window.setTimeout(resolve, 550));

    expect(result.current.sessions).toEqual([]);
    expect(localStorage.getItem('tc-chat-sessions')).toBeNull();
  });
});
