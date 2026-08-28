import { createRef, type ComponentProps } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ChatMessage } from '../../lib/api';
import MessageList from './MessageList';
import { expectNoA11yViolations } from '../../test/a11y';

vi.mock('../../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => ({
  assistantGenerating: 'TrinaxAI is preparing the response…',
  thinking: 'TrinaxAI is thinking',
  thinkingDetails: 'The reasoning will appear here while TrinaxAI works.',
  thoughtFor: 'TrinaxAI thought for {seconds} seconds',
  copy: 'Copy',
  copied: 'Copied',
  regenerate: 'Regenerate',
  listen: 'Listen',
  stop: 'Stop',
  clickToEdit: 'Edit',
  saveAndResend: 'Save',
  cancel: 'Cancel',
  userAvatar: 'User',
  attachedImage: 'Attached image',
  truncated: 'Truncated',
  scrollToBottom: 'Scroll to bottom',
  completionPending: 'Response interrupted: you can continue.',
  completionLimitReached: 'Continuation limit reached.',
  continueResponse: 'Continue',
  requestCancelled: 'Request cancelled.',
  completionError: 'Response did not finish correctly.',
  collectionEmpty: 'La colección seleccionada no contiene documentos indexados.',
  openIndexing: 'Open indexing',
}[key] || key) }) }));
vi.mock('../Sources', () => ({ default: () => null }));
vi.mock('./ChatMarkdown', () => ({ default: ({ text }: { text: string }) => <p>{text}</p> }));

const callbacks = {
  onScroll: vi.fn(), onEditingTextChange: vi.fn(), onCancelEdit: vi.fn(), onSaveEdit: vi.fn(),
  onStartEdit: vi.fn(), onRegenerate: vi.fn(), onCopy: vi.fn(), onSpeak: vi.fn(), onStopSpeak: vi.fn(),
  onOpenAttachment: vi.fn(), onScrollToBottom: vi.fn(), onContinue: vi.fn(),
};

function renderList(messages: Array<ChatMessage & { id?: string | number }>, extra: Partial<ComponentProps<typeof MessageList>> = {}) {
  const props: ComponentProps<typeof MessageList> = {
    messages,
    streaming: false,
    streamedText: '',
    isDark: false,
    userDisplayName: 'U',
    messagesRef: createRef<HTMLDivElement>(),
    editInputRef: createRef<HTMLTextAreaElement>(),
    editingIndex: null,
    editingText: '',
    copiedKey: null,
    ttsSupported: false,
    ttsActiveKey: null,
    showScrollButton: false,
    activeCollections: [],
    ...callbacks,
    ...extra,
  };
  const view = render(<MessageList {...props} />);
  return {
    ...view,
    rerenderList(nextMessages: Array<ChatMessage & { id?: string | number }>, nextExtra: Partial<ComponentProps<typeof MessageList>> = {}) {
      view.rerender(<MessageList {...props} messages={nextMessages} {...nextExtra} />);
    },
  };
}

describe('assistant message bubble', () => {
  it('offers the indexing screen when the selected collection is empty', async () => {
    const onOpenIndexing = vi.fn();
    const user = userEvent.setup();
    renderList([
      { role: 'assistant', content: 'The selected collection contains no indexed documents.' },
    ], { onOpenIndexing });

    expect(screen.getByText('La colección seleccionada no contiene documentos indexados.')).toBeInTheDocument();
    expect(screen.queryByText('The selected collection contains no indexed documents.')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Open indexing' }));

    expect(onOpenIndexing).toHaveBeenCalledOnce();
  });

  it('shows the final answer without exposing stored reasoning', async () => {
    renderList([
      { role: 'assistant', content: 'Respuesta final', thinking: 'Paso interno', thinkingDurationMs: 1200 },
    ]);

    expect(screen.getByText('Respuesta final')).toBeInTheDocument();
    expect(screen.queryByText('Paso interno')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /thinking|thought for/i })).not.toBeInTheDocument();
    await expectNoA11yViolations(document.body);
  });

  it('shows the activity copy and small dots without exposing reasoning text', () => {
    const activity = 'TrinaxAI is analyzing your request';
    renderList([], { streaming: true, activityLabel: activity });

    const status = screen.getByRole('status', { name: activity });
    expect(status).toBeInTheDocument();
    expect(screen.getByText(activity)).toBeInTheDocument();
    expect(screen.queryByText('private reasoning')).not.toBeInTheDocument();
    expect(screen.queryByText(/thought for/i)).not.toBeInTheDocument();
    expect(status.querySelectorAll('.chat-generating-dots span')).toHaveLength(3);
    expect(document.querySelector('.chat-assistant-avatar')).toHaveClass('chat-assistant-avatar-light');
  });

  it('replaces the generating indicator with the streamed answer', () => {
    renderList([], { streaming: true, streamedText: 'Respuesta en curso' });

    expect(screen.getByText('Respuesta en curso')).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('windows long conversations while keeping the initial viewport mounted', () => {
    const messages = Array.from({ length: 200 }, (_, index) => ({
      id: `message-${index}`,
      role: index % 2 ? 'assistant' : 'user',
      content: `message-${index}`,
    })) as Array<ChatMessage & { id: string }>;

    renderList(messages);

    expect(document.querySelectorAll('.chat-row').length).toBeLessThan(messages.length);
    expect(screen.getByText('message-0')).toBeInTheDocument();
    expect(screen.queryByText('message-199')).not.toBeInTheDocument();
  });

  it('keeps the visible anchor when an earlier message is inserted', () => {
    const messages = Array.from({ length: 80 }, (_, index) => ({
      id: `message-${index}`,
      role: 'user' as const,
      content: `message-${index}`,
    }));
    const view = renderList(messages);
    const scrollElement = document.querySelector('.chat-messages') as HTMLDivElement;
    Object.defineProperties(scrollElement, {
      clientHeight: { configurable: true, value: 240 },
      scrollHeight: { configurable: true, value: 20_000 },
    });
    scrollElement.scrollTop = 1_000;
    fireEvent.scroll(scrollElement);

    view.rerenderList([
      { id: 'inserted', role: 'assistant', content: 'inserted' },
      ...messages,
    ]);

    expect(scrollElement.scrollTop).toBe(1_112);
  });

  it('renders the streaming row after scrolling through a long conversation', () => {
    const messages = Array.from({ length: 160 }, (_, index) => ({
      id: `message-${index}`,
      role: 'user' as const,
      content: `message-${index}`,
    }));
    renderList(messages, { streaming: true, streamedText: 'streaming answer' });
    const scrollElement = document.querySelector('.chat-messages') as HTMLDivElement;
    scrollElement.scrollTop = 100_000;
    fireEvent.scroll(scrollElement);

    expect(screen.getByText('streaming answer')).toBeInTheDocument();
    expect(screen.queryByText('message-0')).not.toBeInTheDocument();
  });

  it('keeps an identified message mounted when an earlier message is inserted', () => {
    const messages = [
      { id: 'first', role: 'user', content: 'Primero' },
      { id: 'second', role: 'user', content: 'Segundo' },
    ] as Array<ChatMessage & { id: string }>;
    const view = renderList(messages, { editingIndex: 1, editingText: 'Segundo' });
    const textarea = screen.getByRole('textbox');
    textarea.focus();

    view.rerenderList([
      { id: 'inserted', role: 'assistant', content: 'Insertado' },
      ...messages,
    ], { editingIndex: 2 });

    expect(document.activeElement).toBe(textarea);
  });

  it('keeps legacy messages mounted with deterministic fallback keys', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Primero' },
      { role: 'user', content: 'Segundo' },
    ];
    const view = renderList(messages, { editingIndex: 1, editingText: 'Segundo' });
    const textarea = screen.getByRole('textbox');
    textarea.focus();

    view.rerenderList([
      { role: 'assistant', content: 'Insertado' },
      ...messages,
    ], { editingIndex: 2 });

    expect(document.activeElement).toBe(textarea);
  });

  it('disambiguates repeated ids and legacy messages', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    renderList([
      { id: 'duplicate', role: 'user', content: 'Uno' },
      { id: 'duplicate', role: 'assistant', content: 'Dos' },
      { role: 'user', content: 'Legacy' },
      { role: 'user', content: 'Legacy' },
    ]);

    expect(consoleError).not.toHaveBeenCalledWith(expect.stringContaining('same key'));
  });


  it('exposes a bounded continuation when a stream ended at its limit', async () => {
    const onContinue = vi.fn();
    const user = userEvent.setup();
    renderList([
      { role: 'assistant', content: 'Respuesta parcial', completionStatus: 'pending', canContinue: true, continuationCount: 2, maxContinuations: 2 },
    ], { onContinue });

    expect(screen.getByRole('status')).toHaveTextContent('Continuation limit reached.');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(onContinue).toHaveBeenCalledWith(0);
  });
});
