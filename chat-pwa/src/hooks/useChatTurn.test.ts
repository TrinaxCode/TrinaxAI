import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatMessage, ResearchResult } from '../lib/api';
import type { TurnRouteDecision } from '../components/chat/modeRouter';
import { researchExportMetadata, useChatTurn } from './useChatTurn';

const apiMocks = vi.hoisted(() => ({
  buildWebSearchQuery: vi.fn(() => ({ searchQuery: 'focused query', context: 'prior context' })),
  getRelevantMemoryContext: vi.fn(),
  mergeContinuation: vi.fn((current: string, next: string) => `${current}${next}`),
  runResearch: vi.fn(),
  thinkingModeEnabled: vi.fn(() => true),
}));

const authMocks = vi.hoisted(() => ({
  deviceSessionHasScope: vi.fn(() => true),
  isLocalHostBrowser: vi.fn(() => true),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  ...apiMocks,
}));

vi.mock('../lib/authHeaders', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/authHeaders')>(),
  ...authMocks,
}));

const chatRoute: TurnRouteDecision = {
  mode: 'chat', source: 'manual', reason: 'test', webSearch: false, depth: 1, announce: false,
};
const webRoute: TurnRouteDecision = {
  mode: 'web', source: 'manual', reason: 'test', webSearch: true, depth: 1, announce: false,
};

function turnOptions(overrides: Partial<Parameters<typeof useChatTurn>[0]> = {}): Parameters<typeof useChatTurn>[0] {
  return {
    appendResponseToken: vi.fn(),
    assistantErrorMessage: (error) => error instanceof Error ? error.message : String(error),
    callModeRef: { current: false },
    engine: 'ollama',
    finishResponseSpeech: vi.fn(),
    folderContext: [],
    lang: 'en',
    publishMessages: vi.fn(),
    queueVoiceRestart: vi.fn(),
    researchAbortRef: { current: null },
    resetResponseSpeech: vi.fn(),
    sendMessage: vi.fn(),
    setResearching: vi.fn(),
    setWebSearchAvailable: vi.fn(),
    setWebSearchMode: vi.fn(),
    speakWithFallback: vi.fn(),
    startActivity: vi.fn(),
    startExternalStream: vi.fn(() => ({
      onToken: vi.fn(),
      finish: vi.fn(async (text: string) => text),
      cancel: vi.fn(),
    })),
    stopActivity: vi.fn(),
    t: (key) => key,
    temporary: false,
    wasAborted: () => false,
    webSearchAvailable: true,
    ...overrides,
  };
}

describe('useChatTurn', () => {
  beforeEach(() => {
    apiMocks.getRelevantMemoryContext.mockReset();
    apiMocks.runResearch.mockReset();
    authMocks.deviceSessionHasScope.mockReturnValue(true);
    authMocks.isLocalHostBrowser.mockReturnValue(true);
  });

  it('builds isolated context from related chats and relevant memory', async () => {
    apiMocks.getRelevantMemoryContext.mockResolvedValue([{ fact: 'prefers concise answers' }]);
    const options = turnOptions({
      folderContext: [{
        title: 'Earlier work',
        messages: [
          { role: 'system', content: 'ignored' },
          { role: 'user', content: 'Remember this' },
          { role: 'assistant', content: 'Noted' },
        ],
      }],
    });
    const { result } = renderHook(() => useChatTurn(options));
    let context: ChatMessage[] = [];

    await act(async () => {
      context = await result.current.buildTurnContextMessages([{ role: 'user', content: 'What do I prefer?' }]);
    });

    expect(apiMocks.getRelevantMemoryContext).toHaveBeenCalledWith('What do I prefer?');
    expect(context).toHaveLength(2);
    expect(context[0].content).toContain('CHAT "Earlier work"');
    expect(context[0].content).not.toContain('ignored');
    expect(context[1].content).toContain('prefers concise answers');
  });

  it('hands an agent turn off without starting chat inference', async () => {
    const onAgentHandoff = vi.fn();
    const options = turnOptions({ onAgentHandoff });
    const { result } = renderHook(() => useChatTurn(options));
    const messages: ChatMessage[] = [
      { role: 'user', content: 'old request' },
      { role: 'assistant', content: 'old response' },
      { role: 'user', content: 'do this' },
    ];

    await act(() => result.current.dispatchTurn({
      persistedMessages: messages,
      prompt: 'do this',
      route: { ...chatRoute, mode: 'agent' },
      collections: ['default'],
    }));

    expect(onAgentHandoff).toHaveBeenCalledWith(expect.objectContaining({
      prompt: 'do this',
      context: messages.slice(0, -1),
    }));
    expect(options.sendMessage).not.toHaveBeenCalled();
  });

  it('publishes grounded streamed web research with audit metadata', async () => {
    const source = { file: 'web', project: 'web', snippet: 'evidence', score: 1, kind: 'web', url: 'https://example.com' };
    const research: ResearchResult = {
      answer: ' researched answer ', sub_questions: ['q1'], sources: [source], passes: 2,
      model: 'model', web_search: true, web_provider: 'provider', search_query: 'focused query',
      finish_reason: 'stop', completion_status: 'complete',
    };
    apiMocks.runResearch.mockImplementation(async (_query, options) => {
      options?.onToken?.('researched', 'researched');
      return research;
    });
    const publishMessages = vi.fn();
    const options = turnOptions({ publishMessages });
    const { result } = renderHook(() => useChatTurn(options));

    await act(() => result.current.dispatchTurn({
      persistedMessages: [{ role: 'user', content: 'latest facts' }],
      prompt: 'latest facts', route: webRoute, collections: ['default'],
    }));

    expect(apiMocks.runResearch).toHaveBeenCalledWith('latest facts', expect.objectContaining({
      webSearch: true, searchQuery: 'focused query', includeLocal: false,
    }));
    expect(publishMessages).toHaveBeenCalledWith([
      expect.objectContaining({ role: 'user' }),
      expect.objectContaining({
        role: 'assistant', content: 'researched answer', sources: [source],
        research: expect.objectContaining({ web_provider: 'provider', passes: 2 }),
      }),
    ]);
    expect(options.setResearching).toHaveBeenNthCalledWith(1, true);
    expect(options.setResearching).toHaveBeenLastCalledWith(false);
  });

  it('blocks web research before network access when the browser lacks authority', async () => {
    authMocks.isLocalHostBrowser.mockReturnValue(false);
    authMocks.deviceSessionHasScope.mockReturnValue(false);
    const onWebSearchBlocked = vi.fn();
    const queueVoiceRestart = vi.fn();
    const options = turnOptions({
      callModeRef: { current: true }, onWebSearchBlocked, queueVoiceRestart,
    });
    const { result } = renderHook(() => useChatTurn(options));

    await act(() => result.current.dispatchTurn({
      persistedMessages: [], prompt: 'search', route: webRoute, collections: [],
      viaVoice: true, continueCall: true,
    }));

    expect(onWebSearchBlocked).toHaveBeenCalledOnce();
    expect(queueVoiceRestart).toHaveBeenCalledWith(800);
    expect(apiMocks.runResearch).not.toHaveBeenCalled();
  });

  it('allows web research for a paired remote device with web scope', async () => {
    authMocks.isLocalHostBrowser.mockReturnValue(false);
    authMocks.deviceSessionHasScope.mockReturnValue(true);
    apiMocks.runResearch.mockResolvedValue({
      answer: 'remote answer',
      sub_questions: [],
      sources: [{ file: 'web', project: 'web', snippet: 'evidence', score: 1, kind: 'web', url: 'https://example.com' }],
      passes: 1,
      model: 'model',
      web_search: true,
      web_provider: 'provider',
    });
    const onWebSearchBlocked = vi.fn();
    const options = turnOptions({ onWebSearchBlocked });
    const { result } = renderHook(() => useChatTurn(options));

    await act(() => result.current.dispatchTurn({
      persistedMessages: [{ role: 'user', content: 'search' }],
      prompt: 'search', route: webRoute, collections: [],
    }));

    expect(onWebSearchBlocked).not.toHaveBeenCalled();
    expect(apiMocks.runResearch).toHaveBeenCalledOnce();
  });

  it('continues a truncated text response and publishes the merged result', async () => {
    const sendMessage = vi.fn()
      .mockResolvedValueOnce({
        content: 'first ', thinking: 'thought one', thinkingDurationMs: 8,
        meta: { finishReason: 'length', canContinue: true, maxContinuations: 2 },
      })
      .mockResolvedValueOnce({
        content: 'second', thinking: 'thought two', thinkingDurationMs: 12,
        meta: { finishReason: 'stop', completionStatus: 'complete', canContinue: false },
      });
    const publishMessages = vi.fn();
    const options = turnOptions({ sendMessage, publishMessages });
    const { result } = renderHook(() => useChatTurn(options));

    await act(() => result.current.dispatchTurn({
      persistedMessages: [{ role: 'user', content: 'long answer' }],
      prompt: 'long answer', route: chatRoute, collections: ['docs'],
    }));

    expect(sendMessage).toHaveBeenCalledTimes(2);
    expect(apiMocks.mergeContinuation).toHaveBeenCalledWith('first ', 'second');
    expect(publishMessages).toHaveBeenCalledWith([
      expect.objectContaining({ role: 'user' }),
      expect.objectContaining({
        role: 'assistant', content: 'first second', thinking: 'thought one\nthought two',
        continuationCount: 1, completionStatus: 'complete',
      }),
    ]);
  });

  it('publishes cancellation and ordinary inference failures safely', async () => {
    const cancelledPublish = vi.fn();
    const cancelledOptions = turnOptions({
      publishMessages: cancelledPublish,
      sendMessage: vi.fn().mockResolvedValue({ content: '', meta: {} }),
      wasAborted: () => true,
    });
    const cancelled = renderHook(() => useChatTurn(cancelledOptions));
    await act(() => cancelled.result.current.dispatchTurn({
      persistedMessages: [], prompt: 'cancel', route: chatRoute, collections: [],
    }));
    expect(cancelledPublish).toHaveBeenCalledWith([
      expect.objectContaining({ content: '_requestCancelled_', completionStatus: 'cancelled' }),
    ]);

    const failedPublish = vi.fn();
    const failedOptions = turnOptions({
      publishMessages: failedPublish,
      sendMessage: vi.fn().mockRejectedValue(new Error('model failed')),
    });
    const failed = renderHook(() => useChatTurn(failedOptions));
    await act(() => failed.result.current.dispatchTurn({
      persistedMessages: [], prompt: 'fail', route: chatRoute, collections: [],
      continueCall: true,
    }));
    expect(failedPublish).toHaveBeenCalledWith([
      expect.objectContaining({ content: 'model failed' }),
    ]);
  });
});

describe('researchExportMetadata', () => {
  it('normalizes an empty search query away from persisted metadata', () => {
    expect(researchExportMetadata({
      answer: 'answer', sub_questions: [], sources: [], passes: 1, model: 'model', search_query: '',
    })).toEqual(expect.objectContaining({ search_query: undefined, passes: 1 }));
  });
});
