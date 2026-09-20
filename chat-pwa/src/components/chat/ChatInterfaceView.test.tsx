import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('./AttachmentPreview', () => ({ default: (props: any) => <button onClick={props.onClose}>attachment-preview</button> }));
vi.mock('./ChatHeader', () => ({ default: (props: any) => <div><button onClick={props.onMenuToggle}>menu</button><button onClick={() => props.onEngineChange('rag')}>engine</button><button onClick={() => props.onResearchModeChange(true)}>research</button><button onClick={() => props.onWebSearchModeChange(true)}>web</button><button onClick={() => props.onExportMarkdown()}>export-md</button>{props.onOpenAgent && <button onClick={props.onOpenAgent}>agent</button>}</div> }));
vi.mock('./MessageList', () => ({ default: (props: any) => <div><button onClick={() => props.onStartEdit(0)}>edit</button><button onClick={() => props.onRegenerate(1)}>regenerate</button><button onClick={() => props.onContinue(1)}>continue</button><button onClick={() => props.onCopy('text', 'key')}>copy</button><button onClick={() => props.onSpeak('text', 'key')}>speak</button><button onClick={props.onStopSpeak}>stop-speak</button><button onClick={props.onOpenIndexing}>open-indexing</button></div> }));
vi.mock('./ChatComposer', () => ({ default: (props: any) => <div><button onClick={props.onToggleCollection}>collection</button><button onClick={() => props.onAttachmentMenuChange(true)}>attachments</button><button onClick={props.onToggleCall}>call</button><button onClick={props.onToggleDictation}>dictation</button><button onClick={props.onStop}>stop</button><button onClick={props.onSend}>send</button></div> }));
vi.mock('./EmptyChat', () => ({ default: ({ chips }: any) => <div>{chips.map((chip: any) => <button key={chip.idx} onClick={chip.action}>{chip.label}</button>)}</div> }));
vi.mock('./SpeakingIndicator', () => ({ default: ({ speaking }: any) => <span data-speaking={String(speaking)}>speaking</span> }));
vi.mock('./VoiceCallView', () => ({ default: (props: any) => <button onClick={props.onEnd}>end-call</button> }));

import { ChatInterfaceView } from './ChatInterfaceView';

function controller(overrides: Record<string, unknown> = {}) {
  const fn = () => vi.fn();
  return {
    activeCollectionsForRequest: ['default'], activeCollectionIds: ['default'], activityLabel: '', attachmentMenuRef: { current: null }, attachedDocs: [], attachedImages: [], attachmentMenuOpen: false, busy: false, callMode: false, canOpenPreview: false, clearAttachedDocs: fn(), clearDragActive: fn(), collections: [], continueResponse: fn(), copiedKey: null, copyMessage: fn(), customPrompts: { current: [] }, displayChips: [{ label: 'chip', icon: '', action: fn(), idx: 0 }], docConvertProgress: null, docIndexCollectionId: 'default', docInputRef: { current: null }, docUploadStatus: '', downloadPreviewAttachment: fn(), dragActive: false, editInputRef: { current: null }, editingIndex: null, editingText: '', engine: 'ollama', exportMenuOpen: false, exportPdf: fn(), exportMarkdown: fn(), exportWord: fn(), fileInputRef: { current: null }, handleDragEnter: fn(), handleDragLeave: fn(), handleDragOver: fn(), handleDrop: fn(), handleInputChange: fn(), handleKeyDown: fn(), handlePaste: fn(), handlePromptSelect: fn(), handleSend: fn(), handleStop: fn(), imageError: '', indexAttachedDocs: fn(), input: '', inputRef: { current: null }, isDark: false, isMobile: false, listening: false, messages: [], messagesRef: { current: null }, motd: 'motd', onEngineChange: fn(), onMenuToggle: fn(), onNavigate: fn(), onPickDocs: fn(), onPickImage: fn(), openInBrowser: fn(), openPreviewAttachment: fn(), openStoredAttachment: fn(), placeholder: 'placeholder', previewAttachment: null, quickChipRotation: 0, regenerateFrom: fn(), researchMode: false, saveEdit: fn(), showScrollButton: false, scrollToBottom: fn(), setAttachedImages: fn(), setAttachmentMenuOpen: fn(), setDocIndexCollectionId: fn(), setEditingIndex: fn(), setEditingText: fn(), setExportMenuOpen: fn(), setPreviewAttachment: fn(), setResearchMode: fn(), slashFilter: '', slashOpen: false, speak: fn(), startEdit: fn(), stopSpeak: fn(), streamedText: '', streaming: false, temporary: false, textPreview: null, t: (key: string) => key, toggleCollection: fn(), toggleDictation: fn(), toggleVoice: fn(), ttsActiveKey: null, ttsSpeaking: false, ttsSupported: false, updateScrollState: fn(), userDisplayName: 'User', voiceSupported: false, webSearchAvailable: true, webSearchMode: false, handleWebSearchModeChange: fn(), ...overrides,
  } as any;
}

describe('chat interface composition', () => {
  it('renders the empty chat flow, drop overlay, and delegates controls', () => {
    const c = controller({ dragActive: true, temporary: true });
    const { container } = render(<ChatInterfaceView controller={c} />);
    expect(screen.getByText('dropFilesHere')).toBeInTheDocument();
    expect(screen.getByText('temporaryChatDescription')).toBeInTheDocument();
    fireEvent.paste(container.firstChild!, { clipboardData: {} });
    fireEvent.dragEnter(container.firstChild!);
    fireEvent.dragOver(container.firstChild!);
    fireEvent.dragLeave(container.firstChild!);
    fireEvent.drop(container.firstChild!);
    fireEvent.dragEnd(container.firstChild!);
    for (const name of ['menu', 'engine', 'research', 'web', 'export-md', 'agent', 'edit', 'regenerate', 'continue', 'copy', 'speak', 'stop-speak', 'open-indexing', 'collection', 'attachments', 'call', 'dictation', 'stop', 'send', 'chip']) {
      const button = screen.queryByRole('button', { name });
      if (button) fireEvent.click(button);
    }
    expect(c.handlePaste).toHaveBeenCalled();
    expect(c.onNavigate).toHaveBeenCalled();
    expect(c.handleSend).toHaveBeenCalled();
  });

  it('switches to voice call view and always renders attachment preview', () => {
    const c = controller({ callMode: true, listening: true, ttsSpeaking: true, previewAttachment: { attachment: {}, url: 'blob:x' } });
    render(<ChatInterfaceView controller={c} />);
    fireEvent.click(screen.getByRole('button', { name: 'end-call' }));
    fireEvent.click(screen.getByRole('button', { name: 'attachment-preview' }));
    expect(c.toggleVoice).toHaveBeenCalled();
    expect(c.setPreviewAttachment).toHaveBeenCalled();
  });
});
