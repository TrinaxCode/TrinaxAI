import { createRef, type ComponentProps } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Collection } from '../../lib/api';
import ChatComposer from './ChatComposer';

vi.mock('../../i18n/I18nContext', () => ({
  useI18n: () => ({
    lang: 'en',
    t: (key: string) => ({
      activeCollections: 'Active collections',
      expandComposer: 'Expand composer',
      closeExpandedComposer: 'Close expanded composer',
      attachImage: 'Attach image',
      attachDocument: 'Attach document',
      startDictation: 'Start dictation',
      stopDictation: 'Stop dictation',
      dictationUnavailable: 'Dictation unavailable',
      voiceMode: 'Voice mode',
      exitVoiceMode: 'Exit voice mode',
      send: 'Send',
      stop: 'Stop',
      removeDocument: 'Remove document',
      removeImage: 'Remove image',
      truncated: 'truncated',
      indexAttachedQuestion: 'Index attached?',
      indexAttachedNow: 'Index now',
      builtInCommand: 'Built-in',
    }[key] || key),
  }),
}));

const collection: Collection = { id: 'default', name: 'General', created_at: 1, updated_at: 1 };

function renderComposer(overrides: Partial<ComponentProps<typeof ChatComposer>> = {}) {
  const actions = {
    onToggleCollection: vi.fn(),
    onDocIndexCollectionChange: vi.fn(),
    onIndexAttachedDocs: vi.fn(),
    onClearDocs: vi.fn(),
    onRemoveImage: vi.fn(),
    onPickImage: vi.fn(),
    onPickDocs: vi.fn(),
    onAttachmentMenuChange: vi.fn(),
    onPromptSelect: vi.fn(),
    onInputChange: vi.fn(),
    onKeyDown: vi.fn(),
    onToggleCall: vi.fn(),
    onToggleDictation: vi.fn(),
    onStop: vi.fn(),
    onSend: vi.fn(),
  };
  const props: ComponentProps<typeof ChatComposer> = {
    engine: 'rag',
    isDark: false,
    collections: [collection],
    activeCollectionIds: ['default'],
    docUploadStatus: '',
    docConvertProgress: null,
    attachedDocs: [],
    docIndexCollectionId: 'default',
    attachedImages: [],
    imageError: '',
    streaming: false,
    attachmentMenuOpen: false,
    slashOpen: false,
    slashFilter: '',
    prompts: [],
    input: '',
    placeholder: 'Ask TrinaxAI',
    voiceSupported: true,
    callMode: false,
    listening: false,
    inputRef: createRef<HTMLTextAreaElement>(),
    fileInputRef: createRef<HTMLInputElement>(),
    docInputRef: createRef<HTMLInputElement>(),
    attachmentMenuRef: createRef<HTMLDivElement>(),
    ...actions,
    ...overrides,
  };
  return { ...render(<ChatComposer {...props} />), actions, props };
}

describe('ChatComposer release paths', () => {
  it('renders document/image progress, indexing and removes attachments', async () => {
    const user = userEvent.setup();
    const { actions } = renderComposer({
      attachedDocs: [{ name: 'guide.md', size: 12, content: 'hello', file: new File(['hello'], 'guide.md'), truncated: true }],
      attachedImages: [{ dataUrl: 'data:image/png;base64,abc', file: new File(['x'], 'shot.png') }],
      docUploadStatus: 'Uploading',
      docConvertProgress: { file: 'guide.md', progress: 120 },
      imageError: 'Invalid image',
    });
    expect(screen.getByRole('status')).toHaveTextContent('Uploading');
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '120');
    expect(screen.getByText('guide.md')).toBeInTheDocument();
    expect(screen.getByText('truncated')).toBeInTheDocument();
    expect(screen.getByText('Invalid image')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Remove document' }));
    await user.click(screen.getByRole('button', { name: 'Remove image 1' }));
    await user.click(screen.getByRole('button', { name: 'Index now' }));
    expect(actions.onClearDocs).toHaveBeenCalledOnce();
    expect(actions.onRemoveImage).toHaveBeenCalledWith(0);
    expect(actions.onIndexAttachedDocs).toHaveBeenCalledOnce();
  });

  it('opens attachment and slash menus, toggles context, and handles shortcuts', async () => {
    const user = userEvent.setup();
    const prompt = { name: 'help', text: 'Show help', builtin: true as const, kind: 'noop' as const };
    const { container, actions } = renderComposer({
      activeCollectionIds: [],
      attachmentMenuOpen: true,
      slashOpen: true,
      slashFilter: 'he',
      prompts: [prompt, { name: 'other', text: 'Other' }],
    });
    await user.click(screen.getByRole('button', { name: 'General' }));
    expect(actions.onToggleCollection).toHaveBeenCalledWith('default');
    await user.click(screen.getByRole('menuitem', { name: 'Attach image' }));
    expect(actions.onAttachmentMenuChange).toHaveBeenCalledWith(false);
    await user.click(screen.getByRole('button', { name: /\/help/ }));
    expect(actions.onPromptSelect).toHaveBeenCalledWith(prompt);

    const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.keyDown(document, { key: '/', cancelable: true });
    expect(textarea).toHaveFocus();
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true, cancelable: true });
    fireEvent.keyDown(textarea, { key: '/', cancelable: true });
    expect(actions.onKeyDown).toHaveBeenCalledOnce();
  });

  it('covers call/voice/send/stop states and dark streaming layout', async () => {
    const user = userEvent.setup();
    const { actions, rerender, props } = renderComposer({ input: '' });
    await user.click(screen.getByRole('button', { name: 'Voice mode' }));
    expect(actions.onToggleCall).toHaveBeenCalledOnce();

    rerender(<ChatComposer {...props} input="hello" attachedDocs={[]} attachedImages={[]} />);
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(actions.onSend).toHaveBeenCalledOnce();

    rerender(<ChatComposer {...props} streaming voiceSupported={false} listening={true} isDark input="hello" />);
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Stop' }));
    expect(actions.onStop).toHaveBeenCalledOnce();
  });
});
