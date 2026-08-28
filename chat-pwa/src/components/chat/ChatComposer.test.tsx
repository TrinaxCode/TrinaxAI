import { createRef, type ComponentProps } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Collection } from '../../lib/api';
import ChatComposer from './ChatComposer';

vi.mock('../../i18n/I18nContext', () => ({
  useI18n: () => ({
    lang: 'es',
    t: (key: string) => ({
      activeCollections: 'Contexto',
      expandComposer: 'Ampliar editor',
      closeExpandedComposer: 'Cerrar editor ampliado',
      attachImage: 'Adjuntar imagen',
      attachDocument: 'Adjuntar documento',
      startDictation: 'Iniciar dictado',
      dictationUnavailable: 'El dictado no está disponible',
      voiceMode: 'Modo llamada',
      exitVoiceMode: 'Salir del modo llamada',
      send: 'Enviar',
    }[key] || key),
  }),
}));

const collection: Collection = {
  id: 'default',
  name: 'General',
  created_at: 1,
  updated_at: 1,
};

function renderComposer(engine: 'ollama' | 'rag', onToggleCollection = vi.fn()) {
  const props: ComponentProps<typeof ChatComposer> = {
    engine,
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
    placeholder: 'Escribe un mensaje',
    voiceSupported: false,
    callMode: false,
    listening: false,
    inputRef: createRef<HTMLTextAreaElement>(),
    fileInputRef: createRef<HTMLInputElement>(),
    docInputRef: createRef<HTMLInputElement>(),
    attachmentMenuRef: createRef<HTMLDivElement>(),
    onToggleCollection,
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
  return render(<ChatComposer {...props} />);
}

describe('ChatComposer RAG context bar', () => {
  it('keeps the collection bar outside the composer flow while preserving its action', async () => {
    const onToggleCollection = vi.fn();
    const { container } = renderComposer('rag', onToggleCollection);
    const bar = container.querySelector('.chat-active-collections');

    expect(bar).toHaveClass('absolute', 'bottom-full');
    expect(bar).not.toHaveClass('bg-[#151515]/95', 'bg-white/95', 'backdrop-blur-xl', 'shadow-lg');
    expect(bar?.parentElement).toHaveClass('relative');
    expect(bar?.nextElementSibling).toHaveClass('relative', 'w-full', 'z-30');

    const general = screen.getByRole('button', { name: 'General' });
    expect(general).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(general);
    expect(onToggleCollection).toHaveBeenCalledWith('default');
  });

  it('does not render the collection bar in Ollama mode', () => {
    const { container } = renderComposer('ollama');

    expect(container.querySelector('.chat-active-collections')).toBeNull();
    expect(screen.queryByRole('button', { name: 'General' })).toBeNull();
  });
});
