import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useChatHistory } from './useChatHistory';

describe('chat history synchronization', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('keeps a newly created blank chat active during a shared refresh', () => {
    localStorage.setItem('tc-chat-sessions', JSON.stringify([{
      id: 'attachments',
      title: 'Attachments',
      engine: 'ollama',
      messages: [{ role: 'user', content: 'stored message' }],
      createdAt: 1,
      updatedAt: 1,
    }]));

    const { result } = renderHook(() => useChatHistory());
    let createdId = '';
    act(() => {
      createdId = result.current.createSession('ollama', 'New Chat').id;
    });
    act(() => {
      window.dispatchEvent(new Event('trinaxai:shared-state-updated'));
    });

    expect(result.current.activeId).toBe(createdId);
    expect(result.current.sessions.map((session) => session.id)).toEqual([createdId, 'attachments']);
  });
});
