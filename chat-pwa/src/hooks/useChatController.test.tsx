import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getCollections: vi.fn(),
  getWebSearchSettings: vi.fn(),
  startLocalAi: vi.fn(),
  formatUserFacingError: vi.fn(() => 'friendly error'),
  thinkingModeEnabled: vi.fn(() => false),
  userFacingErrorDetails: vi.fn(() => ({ canOpenIndexing: false, canStartLocalAi: false, canOpenSettings: false, message: 'error', recovery: 'retry' })),
}));
const stream = vi.hoisted(() => ({
  useStreamChat: vi.fn(() => ({ streaming: false, streamedText: '', sendMessage: vi.fn(), startExternalStream: vi.fn(), abort: vi.fn(), wasAborted: vi.fn(() => false) })),
}));
const voice = vi.hoisted(() => ({
  useChatVoice: vi.fn(() => ({
    appendResponseToken: vi.fn(), callMode: false, callModeRef: { current: false }, cancelPendingCapture: vi.fn(), dictationStopRef: { current: vi.fn() }, finishResponseSpeech: vi.fn(), listening: false, listeningRef: { current: false }, queueVoiceRestart: vi.fn(), resetResponseSpeech: vi.fn(), speak: vi.fn(), speakWithFallback: vi.fn(), startCall: vi.fn(), startDictation: vi.fn(), stopDictation: vi.fn(), stopSpeak: vi.fn(), stopVoice: vi.fn(), ttsActiveKey: null, ttsSpeaking: false, ttsSupported: false, voiceSupported: false,
  })),
}));
const documents = vi.hoisted(() => ({ useChatDocuments: vi.fn(() => ({ attachedDocs: [], clearAttachedDocs: vi.fn(), docConvertProgress: null, docIndexCollectionId: 'default', docInputRef: { current: null }, docUploadStatus: '', indexAttachedDocs: vi.fn(), onPickDocs: vi.fn(), processDocumentFiles: vi.fn(), rebuildStoredDocumentContext: vi.fn(), setDocUploadStatus: vi.fn(), setDocIndexCollectionId: vi.fn() })) }));
const attachments = vi.hoisted(() => ({ useChatAttachments: vi.fn(() => ({ attachedImages: [], canOpenPreview: false, clearDragActive: vi.fn(), dragActive: false, fileInputRef: { current: null }, handleDragEnter: vi.fn(), handleDragLeave: vi.fn(), handleDragOver: vi.fn(), handleDrop: vi.fn(), handlePaste: vi.fn(), imageError: '', onPickImage: vi.fn(), openPreviewAttachment: vi.fn(), openStoredAttachment: vi.fn(), downloadPreviewAttachment: vi.fn(), previewAttachment: null, setAttachedImages: vi.fn(), setPreviewAttachment: vi.fn(), textPreview: null })) }));
const sender = vi.hoisted(() => ({ useChatSend: vi.fn(() => ({ buildTurnContextMessages: vi.fn(), dispatchTurn: vi.fn(), handleSend: vi.fn(), handleKeyDown: vi.fn() })) }));
const actions = vi.hoisted(() => ({ useChatMessageActions: vi.fn(() => ({ startEdit: vi.fn(), saveEdit: vi.fn(), regenerateFrom: vi.fn(), continueResponse: vi.fn() })) }));
const shared = vi.hoisted(() => ({ onSharedStateUpdated: vi.fn(() => () => undefined) }));
const toast = vi.hoisted(() => ({ useToast: vi.fn(() => ({ toast: vi.fn() })) }));
const auth = vi.hoisted(() => ({
  deviceSessionHasScope: vi.fn(() => false),
  isLocalHostBrowser: vi.fn(() => false),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  getCollections: api.getCollections,
  getWebSearchSettings: api.getWebSearchSettings,
  startLocalAi: api.startLocalAi,
  formatUserFacingError: api.formatUserFacingError,
  thinkingModeEnabled: api.thinkingModeEnabled,
  userFacingErrorDetails: api.userFacingErrorDetails,
}));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key, lang: 'en' }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('../components/Toast', () => ({ useToast: toast.useToast }));
vi.mock('../services/audioManager', () => ({ audioManager: { play: vi.fn() } }));
vi.mock('../lib/authHeaders', async (importOriginal) => ({ ...await importOriginal<typeof import('../lib/authHeaders')>(), ...auth }));
vi.mock('../lib/sharedState', () => shared);
vi.mock('./useStreamChat', () => stream);
vi.mock('./useChatVoice', () => voice);
vi.mock('./useChatDocuments', () => documents);
vi.mock('./useChatAttachments', () => attachments);
vi.mock('./useChatSend', () => sender);
vi.mock('./useChatMessageActions', () => actions);
vi.mock('./useWaitingSound', () => ({ useWaitingSound: vi.fn() }));

import { useChatController } from './useChatController';
import type { ChatInterfaceProps } from './useChatController';

const baseProps = (): ChatInterfaceProps => ({
  messages: [], engine: 'ollama', onMessagesChange: vi.fn(), onEngineChange: vi.fn(), onMenuToggle: vi.fn(), onNavigate: vi.fn(), onAgentHandoff: vi.fn(), onWebSearchBlocked: vi.fn(), folderContext: [],
});

function FocusProbe() {
  const controller = useChatController(baseProps());
  return <textarea ref={controller.inputRef} aria-label="chat input" />;
}

describe('chat controller integration surface', () => {
  beforeEach(() => {
    localStorage.clear();
    api.getCollections.mockReset().mockResolvedValue([{ id: 'default', name: 'General', created_at: 1, updated_at: 1 }, { id: 'docs', name: 'Docs', created_at: 1, updated_at: 1 }]);
    api.getWebSearchSettings.mockReset().mockResolvedValue({ enabled: true, preferred_provider: 'duckduckgo' });
    api.startLocalAi.mockReset().mockResolvedValue(undefined);
    auth.deviceSessionHasScope.mockReturnValue(false);
    auth.isLocalHostBrowser.mockReturnValue(false);
    shared.onSharedStateUpdated.mockClear();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { callback(0); return 1; });
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:export');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    vi.spyOn(window, 'open').mockReturnValue({ document: { write: vi.fn(), close: vi.fn() }, focus: vi.fn(), print: vi.fn() } as any);
  });

  it('loads collections, handles input/slash state, and exposes navigation actions', async () => {
    const props = baseProps();
    const { result } = renderHook(() => useChatController(props));
    await waitFor(() => expect(result.current.collections).toHaveLength(2));
    expect(result.current.collections).toHaveLength(2);
    act(() => result.current.handleInputChange({ target: { value: '/res', style: {}, scrollHeight: 30 }, currentTarget: { value: '/res', style: {}, scrollHeight: 30 } } as any));
    expect(result.current.slashOpen).toBe(true);
    expect(result.current.slashFilter).toBe('res');
    act(() => result.current.handleInputChange({ target: { value: 'plain', style: {}, scrollHeight: 30 }, currentTarget: { value: 'plain', style: {}, scrollHeight: 30 } } as any));
    expect(result.current.slashOpen).toBe(false);
    act(() => result.current.toggleCollection('docs'));
    expect(result.current.activeCollectionIds).toContain('docs');
    act(() => result.current.handlePromptSelect({ name: 'settings', text: '', builtin: true, kind: 'navigate_settings' } as any));
    expect(props.onNavigate).toHaveBeenCalledWith('settings');
    act(() => result.current.openInBrowser('guide.md', 'docs'));
    expect((window as any).__tc_browser_open).toEqual({ file: 'guide.md', collection: 'docs' });
    act(() => result.current.handleWebSearchModeChange(true));
    expect(props.onWebSearchBlocked).toHaveBeenCalled();
  });

  it('allows web search mode for a paired remote device with web scope', async () => {
    auth.deviceSessionHasScope.mockReturnValue(true);
    const props = baseProps();
    const { result } = renderHook(() => useChatController(props));

    act(() => result.current.handleWebSearchModeChange(true));

    expect(result.current.webSearchMode).toBe(true);
    expect(props.onWebSearchBlocked).not.toHaveBeenCalled();
  });

  it('restores web search mode on a remote browser instead of forcing localhost', () => {
    localStorage.setItem('tc-web-search-mode', '1');
    auth.deviceSessionHasScope.mockReturnValue(true);
    const { result } = renderHook(() => useChatController(baseProps()));
    expect(result.current.webSearchMode).toBe(true);
  });

  it('does not open the mobile keyboard by focusing on mount', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query === '(max-width: 640px)',
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList);

    render(<FocusProbe />);

    expect(screen.getByRole('textbox', { name: 'chat input' })).not.toHaveFocus();
  });

  it('covers exports, attachment menus, voice toggles, and collection fallback', async () => {
    localStorage.setItem('tc-research-mode', '1');
    const props = baseProps();
    const { result } = renderHook(() => useChatController(props));
    await waitFor(() => expect(api.getWebSearchSettings).toHaveBeenCalled());
    act(() => result.current.setExportMenuOpen(true));
    act(() => result.current.exportMarkdown());
    act(() => result.current.exportWord());
    act(() => result.current.exportPdf());
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2);
    act(() => result.current.setAttachmentMenuOpen(true));
    act(() => result.current.handleStop());
    act(() => result.current.toggleVoice());
    act(() => result.current.toggleDictation());
    act(() => result.current.copyMessage('hello', 'm1'));
    act(() => result.current.setResearchMode(false));
    expect(result.current.displayChips.length).toBeGreaterThan(0);
    act(() => result.current.displayChips[0].action());
  });

});
