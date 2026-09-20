import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  buildWebSearchQuery: vi.fn(() => ({ searchQuery: 'web query', context: 'context' })),
  runResearch: vi.fn(),
  thinkingModeEnabled: vi.fn(() => false),
}));
const audio = vi.hoisted(() => ({ play: vi.fn() }));
const profile = vi.hoisted(() => ({ rememberFromMessage: vi.fn() }));
const storage = vi.hoisted(() => ({ storeChatAttachment: vi.fn() }));
const turn = vi.hoisted(() => ({
  buildTurnContextMessages: vi.fn(async (messages) => messages),
  dispatchTurn: vi.fn(async () => undefined),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  buildWebSearchQuery: api.buildWebSearchQuery,
  runResearch: api.runResearch,
  thinkingModeEnabled: api.thinkingModeEnabled,
}));
vi.mock('../services/audioManager', () => ({ audioManager: audio }));
vi.mock('../lib/userProfile', async (importOriginal) => ({ ...await importOriginal<typeof import('../lib/userProfile')>(), rememberFromMessage: profile.rememberFromMessage }));
vi.mock('../lib/chatAttachments', async (importOriginal) => ({ ...await importOriginal<typeof import('../lib/chatAttachments')>(), storeChatAttachment: storage.storeChatAttachment }));
vi.mock('./useChatTurn', () => ({
  researchExportMetadata: (result: unknown) => ({ exported: result }),
  useChatTurn: () => turn,
}));

import { useChatSend, type UseChatSendOptions } from './useChatSend';
import type { ChatMessage } from '../lib/api';

const t = (key: string) => key;
const file = new File(['text'], 'guide.md', { type: 'text/markdown' });
const image = new File(['image'], 'photo.png', { type: 'image/png' });

function stream() {
  return { onToken: vi.fn(), finish: vi.fn(async (answer: string) => answer), cancel: vi.fn() };
}

function options(overrides: Partial<UseChatSendOptions> = {}): UseChatSendOptions {
  return {
    activeCollectionsForRequest: ['default'],
    appendResponseToken: vi.fn(),
    assistantErrorMessage: vi.fn(() => 'friendly error'),
    attachedDocs: [],
    attachedImages: [],
    busy: false,
    callModeRef: { current: false },
    cancelPendingCapture: vi.fn(),
    clearAttachedDocs: vi.fn(),
    customPrompts: { current: [] },
    engine: 'ollama',
    exportMarkdown: vi.fn(),
    finishResponseSpeech: vi.fn(),
    folderContext: [],
    handleSendTextRef: { current: vi.fn(async () => undefined) },
    input: 'Hello',
    lang: 'en',
    messageStateRef: { current: [] },
    messages: [],
    onMessagesChange: vi.fn(),
    onAgentHandoff: vi.fn(),
    onNavigate: vi.fn(),
    onWebSearchBlocked: vi.fn(),
    publishMessages: vi.fn(),
    queueVoiceRestart: vi.fn(),
    researchAbortRef: { current: null },
    researchMode: false,
    resetInputHeight: vi.fn(),
    resetResponseSpeech: vi.fn(),
    scrollToBottom: vi.fn(),
    sendMessage: vi.fn(async () => ({ content: 'answer', meta: {}, thinking: '', thinkingDurationMs: 1 })),
    setAttachedImages: vi.fn(),
    setDocUploadStatus: vi.fn(),
    setInput: vi.fn(),
    setResearching: vi.fn(),
    setSlashOpen: vi.fn(),
    setWebSearchAvailable: vi.fn(),
    setWebSearchMode: vi.fn(),
    speakWithFallback: vi.fn(),
    startActivity: vi.fn(),
    startExternalStream: vi.fn(stream),
    stopActivity: vi.fn(),
    t,
    temporary: false,
    wasAborted: vi.fn(() => false),
    webSearchAvailable: true,
    webSearchMode: true,
    ...overrides,
  };
}

describe('chat send orchestration', () => {
  beforeEach(() => {
    api.buildWebSearchQuery.mockClear();
    api.runResearch.mockReset();
    audio.play.mockClear();
    profile.rememberFromMessage.mockClear();
    storage.storeChatAttachment.mockReset();
    turn.buildTurnContextMessages.mockClear();
    turn.dispatchTurn.mockClear();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { callback(0); return 1; });
  });

  it('ignores empty, busy, and already-running requests and sends a normal message with attachments', async () => {
    const attachment = { kind: 'document', name: 'guide.md', size: file.size, mimeType: file.type };
    storage.storeChatAttachment.mockResolvedValueOnce(attachment).mockRejectedValueOnce(new Error('storage offline'));
    const opts = options({
      input: '  ',
      attachedImages: [{ file: image, dataUrl: 'data:image/png;base64,x' }],
      attachedDocs: [{ file, name: 'guide.md', size: file.size, content: 'text', truncated: true }],
    });
    const { result, rerender } = renderHook((props) => useChatSend(props), { initialProps: opts });
    await act(async () => { await result.current.handleSend(); });
    expect(opts.publishMessages).toHaveBeenCalled();
    expect(turn.dispatchTurn).toHaveBeenCalledWith(expect.objectContaining({ hasImage: true, hasDocuments: true }));
    expect(profile.rememberFromMessage).toHaveBeenCalledWith('');
    expect(opts.setDocUploadStatus).toHaveBeenCalledWith('chatAttachmentLocalOnly');
    expect(audio.play).toHaveBeenCalledWith('message-send');

    rerender({ ...opts, input: 'ignored', busy: true });
    await act(async () => { await result.current.handleSend(); });
    rerender({ ...opts, input: 'ignored', busy: false, researchAbortRef: { current: new AbortController() } });
    await act(async () => { await result.current.handleSend(); });
  });

  it('handles navigation, export, custom, summarize, and research slash commands', async () => {
    const base = [{ role: 'user' as const, content: 'old' }];
    const opts = options({ messages: base, messageStateRef: { current: base } });
    const { result, rerender } = renderHook((props) => useChatSend(props), { initialProps: opts });
    const commands = ['index', 'browse', 'memory', 'watch'];
    for (const command of commands) {
      rerender({ ...opts, input: `/${command}` });
      await act(async () => { await result.current.handleSend(); });
    }
    expect(opts.onNavigate).toHaveBeenCalledWith('indexing');
    expect(opts.onNavigate).toHaveBeenCalledWith('browser');
    rerender({ ...opts, input: '/export' });
    await act(async () => { await result.current.handleSend(); });
    expect(opts.exportMarkdown).toHaveBeenCalled();

    rerender({ ...opts, input: '/custom tail', customPrompts: { current: [{ name: 'custom', text: 'expanded', builtin: false }] } });
    await act(async () => { await result.current.handleSend(); });
    expect(turn.dispatchTurn).toHaveBeenCalled();

    rerender({ ...opts, input: '/summarize' });
    await act(async () => { await result.current.handleSend(); });
    expect(opts.sendMessage).toHaveBeenCalled();

    api.runResearch.mockResolvedValue({ answer: 'research answer', sources: [], model: 'model', finish_reason: 'stop', completion_status: 'complete' });
    rerender({ ...opts, input: '/research question' });
    await act(async () => { await result.current.handleSend(); });
    expect(api.runResearch).toHaveBeenCalledWith('question', expect.objectContaining({ webSearch: true, searchQuery: 'web query' }));
    expect(opts.onMessagesChange).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ research: expect.anything() })]));
  });

  it('handles temporary research, failed research, and failed summaries', async () => {
    api.runResearch.mockRejectedValue(new Error('offline'));
    const opts = options({ messages: [{ role: 'user', content: 'old' }], input: '/research now' });
    const { result, rerender } = renderHook((props) => useChatSend(props), { initialProps: opts });
    await act(async () => { await result.current.handleSend(); });
    expect(opts.assistantErrorMessage).toHaveBeenCalled();
    expect(opts.setResearching).toHaveBeenCalledWith(false);
    rerender({ ...opts, temporary: true, input: '/research blocked' });
    await act(async () => { await result.current.handleSend(); });
    expect(opts.onMessagesChange).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ content: 'temporaryChatResearchUnavailable' })]));
    const sendMessage = vi.fn(async () => { throw new Error('summary failed'); });
    rerender({ ...opts, temporary: false, input: '/summarize', sendMessage });
    await act(async () => { await result.current.handleSend(); });
    expect(opts.assistantErrorMessage).toHaveBeenCalled();
  });

  it('supports repeated image turns and keyboard send behavior', async () => {
    storage.storeChatAttachment.mockResolvedValue({ kind: 'image', name: 'photo.png', size: image.size, mimeType: image.type });
    const opts = options({ attachedImages: [
      { file: image, dataUrl: 'data:image/png;base64,1' },
      { file: image, dataUrl: 'data:image/png;base64,2' },
    ], input: 'describe' });
    const { result } = renderHook(() => useChatSend(opts));
    await act(async () => { await result.current.handleSend(); });
    expect(turn.dispatchTurn).toHaveBeenCalledTimes(2);
    const event = { key: 'Enter', shiftKey: false, preventDefault: vi.fn() } as any;
    act(() => result.current.handleKeyDown(event));
    expect(event.preventDefault).toHaveBeenCalled();
    act(() => result.current.handleKeyDown({ key: 'Enter', shiftKey: true, preventDefault: vi.fn() } as any));
  });
});
