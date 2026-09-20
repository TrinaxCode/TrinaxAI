import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const deleted = vi.hoisted(() => ({ deleteChatAttachments: vi.fn(async () => undefined) }));
vi.mock('../lib/chatAttachments', () => deleted);

import { useChatMessageActions, type ChatMessageActionsOptions } from './useChatMessageActions';
import type { ChatMessage } from '../lib/api';

const baseMessages: ChatMessage[] = [
  { role: 'user', content: 'Original prompt', displayContent: 'Original prompt', turn: { mode: 'ollama', collections: ['default'] } },
  { role: 'assistant', content: 'Partial answer', canContinue: true, continuationCount: 0 },
];

function options(overrides: Partial<ChatMessageActionsOptions> = {}): ChatMessageActionsOptions {
  return {
    abort: vi.fn(),
    activeCollectionsForRequest: ['default'],
    buildTurnContextMessages: vi.fn(async (messages) => messages),
    busy: false,
    dispatchTurn: vi.fn(async () => undefined),
    editInputRef: { current: null },
    editingIndex: null,
    editingText: '',
    engine: 'ollama',
    lang: 'en',
    messageDisplayContent: (message) => message.displayContent ?? message.content,
    messages: baseMessages,
    onMessagesChange: vi.fn(),
    rebuildStoredDocumentContext: vi.fn(async () => ''),
    sendMessage: vi.fn(async () => ({ content: 'continued', thinking: '', meta: { canContinue: false }, thinkingDurationMs: 2 })),
    setEditingIndex: vi.fn(),
    setEditingText: vi.fn(),
    startActivity: vi.fn(),
    stopActivity: vi.fn(),
    stopSpeak: vi.fn(),
    streaming: false,
    temporary: false,
    ...overrides,
  };
}

describe('chat message actions', () => {
  beforeEach(() => deleted.deleteChatAttachments.mockClear());

  it('starts an edit, cancels a stream, and handles empty edits', () => {
    const editInput = document.createElement('textarea');
    Object.defineProperty(editInput, 'scrollHeight', { value: 80 });
    const opts = options({ streaming: true, editInputRef: { current: editInput } });
    const { result } = renderHook(() => useChatMessageActions(opts));
    act(() => result.current.startEdit(0));
    expect(opts.abort).toHaveBeenCalledWith(true);
    expect(opts.stopSpeak).toHaveBeenCalled();
    expect(opts.setEditingIndex).toHaveBeenCalledWith(0);
    expect(opts.setEditingText).toHaveBeenCalledWith('Original prompt');

    const empty = options({ editingIndex: 0, editingText: '   ' });
    const emptyHook = renderHook(() => useChatMessageActions(empty));
    act(() => { void emptyHook.result.current.saveEdit(); });
    expect(empty.setEditingIndex).toHaveBeenCalledWith(null);
  });

  it('saves edits with durable attachments and dispatches the rebuilt request', async () => {
    const opts = options({ editingIndex: 0, editingText: 'Edited prompt', rebuildStoredDocumentContext: vi.fn(async () => '\n[context]') });
    const { result } = renderHook(() => useChatMessageActions(opts));
    await act(async () => { await result.current.saveEdit(); });
    expect(opts.onMessagesChange).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ role: 'user', content: 'Edited prompt', displayContent: 'Edited prompt' }),
    ]));
    expect(opts.rebuildStoredDocumentContext).toHaveBeenCalled();
    expect(opts.dispatchTurn).toHaveBeenCalledWith(expect.objectContaining({
      prompt: 'Edited prompt',
      requestMessages: expect.arrayContaining([expect.objectContaining({ content: expect.stringContaining('[context]') })]),
    }));
    expect(deleted.deleteChatAttachments).toHaveBeenCalled();
  });

  it('regenerates from an answer, trims router notices, and ignores missing users', async () => {
    const notice: ChatMessage = { role: 'assistant', content: 'router', routerNotice: true };
    const opts = options({ messages: [...baseMessages, notice], streaming: true });
    const { result } = renderHook(() => useChatMessageActions(opts));
    await act(async () => { await result.current.regenerateFrom(2); });
    expect(opts.abort).toHaveBeenCalledWith(true);
    expect(opts.dispatchTurn).toHaveBeenCalledWith(expect.objectContaining({ prompt: 'Original prompt' }));

    const noUser = options({ messages: [{ role: 'assistant', content: 'answer' }] });
    const noUserHook = renderHook(() => useChatMessageActions(noUser));
    await act(async () => { await noUserHook.result.current.regenerateFrom(0); });
    expect(noUser.dispatchTurn).not.toHaveBeenCalled();
  });

  it('continues a response and marks it as errored when the model fails', async () => {
    const opts = options();
    const { result } = renderHook(() => useChatMessageActions(opts));
    await act(async () => { await result.current.continueResponse(1); });
    expect(opts.startActivity).toHaveBeenCalledWith('thinking');
    expect(opts.sendMessage).toHaveBeenCalledWith(expect.any(Array), 'ollama', expect.objectContaining({ collections: ['default'] }));
    expect(opts.onMessagesChange).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ content: 'Partial answercontinued', canContinue: false })]));

    const failing = options({ sendMessage: vi.fn(async () => { throw new Error('offline'); }) });
    const failingHook = renderHook(() => useChatMessageActions(failing));
    await act(async () => { await failingHook.result.current.continueResponse(1); });
    expect(failing.onMessagesChange).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ completionStatus: 'error', canContinue: false })]));

    const blocked = options({ busy: true });
    const blockedHook = renderHook(() => useChatMessageActions(blocked));
    await act(async () => { await blockedHook.result.current.continueResponse(1); });
    expect(blocked.sendMessage).not.toHaveBeenCalled();
  });
});
