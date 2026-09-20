import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AgentInterfaceViewProps } from './AgentInterfaceView';
import { AgentInterfaceView } from './AgentInterfaceView';

vi.mock('../BackButton', () => ({ default: ({ onClick, label }: any) => <button onClick={onClick}>{label}</button> }));
vi.mock('../FolderPicker', () => ({
  default: ({ onSelect, onClose }: any) => <div data-testid="folder-picker"><button onClick={() => onSelect('/picked')}>pick-folder</button><button onClick={onClose}>close-picker</button></div>,
}));
vi.mock('../chat/ChatMarkdown', () => ({ default: ({ text }: any) => <div data-testid="markdown">{text}</div> }));
vi.mock('../chat/ComposerLayout', () => ({
  default: ({ value, onChange, onKeyDown, leftActions, rightActions, inputRef, name, placeholder, disabled }: any) => (
    <div>{leftActions}<textarea ref={inputRef} name={name} aria-label={placeholder} value={value} disabled={disabled} onChange={onChange} onKeyDown={onKeyDown} />{rightActions}</div>
  ),
}));
vi.mock('../ConfirmModal', () => ({
  default: ({ open, title, onConfirm, onCancel }: any) => open ? (
    <div role="dialog" aria-label={title}><button onClick={onConfirm}>{title}-confirm</button><button onClick={onCancel}>{title}-cancel</button></div>
  ) : null,
}));

const ref = () => ({ current: null });
const callback = () => vi.fn();

function props(overrides: Partial<AgentInterfaceViewProps> = {}): AgentInterfaceViewProps {
  return {
    onBack: callback(), isDark: false, t: ((key: string) => key) as any,
    historyOpen: false, historyClosing: false, historyDialogRef: ref(), historyDialogId: 'history', historyTitleId: 'history-title', historyCloseButtonRef: ref(),
    search: '', setSearch: callback(), filteredSessions: [], history: { sessions: [], activeId: null, deleteSession: callback() }, closeHistory: callback(), openSession: callback(), openHistory: callback(),
    pickerOpen: false, workspace: '/work', persistWorkspace: callback(), setPickerOpen: callback(),
    mobileToolsOpen: false, mobileToolsRef: ref(), mainContentRef: ref(), setMobileToolsOpen: callback(),
    running: false, knowledgeSearch: false, setKnowledgeSearch: callback(), webSearch: false, setWebSearch: callback(), deepResearch: false, setDeepResearch: callback(),
    yoloMode: false, handleYoloChange: callback(), modelMode: 'auto', setModelMode: callback(), startNewSession: callback(), setWorkspace: callback(),
    scrollRef: ref(), turns: [], setInput: callback(), inputRef: ref(), editingIndex: null, editingText: '', setEditingText: callback(), saveEdit: callback(), cancelEdit: callback(), startEdit: callback(), copyText: callback(), copiedKey: null, regenerate: callback(),
    agentActivity: '', analyzingImage: false, approve: callback(),
    attachedImage: null, setAttachedImage: callback(), attachedDocs: [], setAttachedDocs: callback(), imageError: '', setImageError: callback(), imageInputRef: ref(), onPickImage: callback(), docInputRef: ref(), onPickDocs: callback(),
    input: '', placeholder: 'prompt', attachmentMenuRef: ref(), attachmentMenuOpen: false, setAttachmentMenuOpen: callback(), dictationAvailable: false, listening: false, toggleDictation: callback(), stop: callback(), send: callback(),
    yoloConfirmOpen: false, setYoloMode: callback(), setYoloConfirmOpen: callback(),
    ...overrides,
  };
}

describe('AgentInterfaceView', () => {
  it('delegates empty-state, header, workspace, mobile tools, and composer controls', () => {
    const p = props({ mobileToolsOpen: true, knowledgeSearch: true, webSearch: true, deepResearch: true, attachmentMenuOpen: true, dictationAvailable: true, input: 'ship it' });
    const view = render(<AgentInterfaceView {...p} />);
    const { container } = view;

    for (const name of ['back', 'agentHistory', 'agentNewSession', 'agentPickFolder', 'quickChipFindBugs', 'agentVoiceMode', 'agentSend']) {
      fireEvent.click(screen.getByRole('button', { name }));
    }
    fireEvent.click(screen.getByRole('switch', { name: 'agentYoloModeOff' }));
    expect(p.onBack).toHaveBeenCalled();
    expect(p.openHistory).toHaveBeenCalled();
    expect(p.startNewSession).toHaveBeenCalled();
    expect(p.setPickerOpen).toHaveBeenCalledWith(true);
    expect(p.setInput).toHaveBeenCalledWith('quickChipFindBugsPrompt');
    expect(p.handleYoloChange).toHaveBeenCalledWith(true);
    expect(p.toggleDictation).toHaveBeenCalled();
    expect(p.send).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'agentTools' }));
    fireEvent.click(screen.getAllByRole('button', { name: 'agentRagOn' })[1]);
    fireEvent.click(screen.getAllByRole('button', { name: 'agentWebSearchOn' })[1]);
    fireEvent.click(screen.getAllByRole('button', { name: 'agentDeepResearch' })[1]);
    fireEvent.change(screen.getAllByRole('combobox', { name: 'agentModel' })[0], { target: { value: 'deep' } });
    expect(p.setKnowledgeSearch).toHaveBeenCalled();
    expect(p.setWebSearch).toHaveBeenCalled();
    expect(p.setDeepResearch).toHaveBeenCalled();
    expect(p.setModelMode).toHaveBeenCalledWith('deep');

    const workspace = screen.getByRole('textbox', { name: 'agentWorkspaceRootLabel' });
    fireEvent.change(workspace, { target: { value: '/next' } });
    expect(p.setWorkspace).toHaveBeenCalledWith('/next');
    view.rerender(<AgentInterfaceView {...p} workspace="/next" />);
    const updatedWorkspace = screen.getByRole('textbox', { name: 'agentWorkspaceRootLabel' });
    fireEvent.blur(updatedWorkspace);
    fireEvent.keyDown(updatedWorkspace, { key: 'Enter' });
    expect(p.persistWorkspace).toHaveBeenCalledWith('/next');

    const menu = screen.getByRole('button', { name: 'agentAttachImage / attachDocument' }).parentElement!;
    fireEvent.click(within(menu).getByRole('button', { name: 'agentAttachImage' }));
    fireEvent.click(screen.getByRole('button', { name: 'attachDocument' }));
    fireEvent.change(container.querySelector('textarea[name="agent-prompt"]')!, { target: { value: 'new prompt' } });
    fireEvent.keyDown(container.querySelector('textarea[name="agent-prompt"]')!, { key: 'Enter' });
    expect(p.setAttachmentMenuOpen).toHaveBeenCalled();
    expect(p.setInput).toHaveBeenCalledWith('new prompt');
  });

  it('covers history deletion, picker selection, dark theme, and YOLO confirmation', () => {
    document.documentElement.lang = 'es';
    const active = { id: 'one', title: '', turns: [], workspace: '/one', createdAt: 1, updatedAt: 1 };
    const other = { id: 'two', title: 'Second', turns: [{ role: 'user' as const, content: 'x' }], workspace: '/two', createdAt: 2, updatedAt: 2 };
    const p = props({
      isDark: true, historyOpen: true, historyClosing: true, search: 'sec', filteredSessions: [active, other],
      history: { sessions: [active, other], activeId: 'one', deleteSession: callback() }, pickerOpen: true, yoloConfirmOpen: true,
    });
    render(<AgentInterfaceView {...p} />);

    expect(screen.getByText('agentUntitled')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'agentSearchHistory' }), { target: { value: 'new' } });
    fireEvent.click(screen.getByText('Second'));
    fireEvent.click(screen.getAllByRole('button', { name: 'delete' })[0]);
    fireEvent.click(screen.getByRole('button', { name: 'delete-confirm' }));
    expect(p.setSearch).toHaveBeenCalledWith('new');
    expect(p.openSession).toHaveBeenCalledWith('two');
    expect(p.history.deleteSession).toHaveBeenCalledWith('one');

    fireEvent.click(screen.getByRole('button', { name: 'pick-folder' }));
    fireEvent.click(screen.getByRole('button', { name: 'close-picker' }));
    expect(p.persistWorkspace).toHaveBeenCalledWith('/picked');
    expect(p.setPickerOpen).toHaveBeenCalledWith(false);

    fireEvent.click(screen.getByRole('button', { name: 'agentYoloConfirmTitle-confirm' }));
    fireEvent.click(screen.getByRole('button', { name: 'agentYoloConfirmTitle-cancel' }));
    expect(p.setYoloMode).toHaveBeenCalledWith(true);
    expect(p.setYoloConfirmOpen).toHaveBeenCalledWith(false);
  });

  it('renders user attachments, completed answers, tool statuses, and approval actions', () => {
    const steps = [
      { id: 'w', tool: 'write_file', dangerous: true, args: { path: 'a.ts', content: 'new' }, status: 'awaiting' as const },
      { id: 'e', tool: 'edit_file', dangerous: true, args: { path: 'b.ts', old: 'old', new: 'new' }, status: 'awaiting' as const },
      { id: 'r', tool: 'run_command', dangerous: true, args: { command: 'npm test' }, status: 'awaiting' as const },
      { id: 'u', tool: 'custom', dangerous: false, args: { value: 'x' }, status: 'awaiting' as const },
      { id: 'd', tool: 'read_file', dangerous: false, args: { path: 'readme' }, status: 'done' as const, result: 'ok' },
      { id: 'x', tool: 'glob', dangerous: false, args: { pattern: '*.ts' }, status: 'denied' as const, result: 'denied' },
      { id: 's', tool: 'web_search', dangerous: false, args: { query: 'TrinaxAI' }, status: 'running' as const },
    ];
    const turns = [
      { role: 'user' as const, content: 'question', image: 'data:image/png;base64,x', documents: [{ name: 'doc.md', truncated: true, preview: 'preview' }] },
      { role: 'assistant' as const, content: 'answer', steps, completionStatus: 'error', model: 'qwen' },
      { role: 'assistant' as const, content: 'cancelled answer', completionStatus: 'cancelled' },
      { role: 'assistant' as const, content: 'pending answer', completionStatus: 'pending' },
    ];
    const p = props({ turns, copiedKey: 'u-0' });
    const view = render(<AgentInterfaceView {...p} />);

    expect(screen.getByAltText('agentAttachImage')).toBeInTheDocument();
    expect(screen.getByText('truncated')).toBeInTheDocument();
    expect(screen.getByText('completionError')).toBeInTheDocument();
    expect(screen.getByText('requestCancelled')).toBeInTheDocument();
    expect(screen.getByText('completionPending')).toBeInTheDocument();
    expect(screen.getAllByText('qwen')).toHaveLength(2);
    screen.getAllByRole('button', { name: 'agentApprove' }).forEach((button) => fireEvent.click(button));
    screen.getAllByRole('button', { name: 'agentReject' }).forEach((button) => fireEvent.click(button));
    expect(p.approve).toHaveBeenCalledTimes(8);
    fireEvent.click(screen.getByRole('button', { name: 'edit' }));
    fireEvent.click(screen.getAllByRole('button', { name: 'copied' })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: 'regenerate' })[0]);
    expect(p.startEdit).toHaveBeenCalledWith(0);
    expect(p.copyText).toHaveBeenCalledWith('question', 'u-0');
    expect(p.regenerate).toHaveBeenCalledWith(1);

    view.rerender(<AgentInterfaceView {...p} copiedKey="a-1" />);
    expect(screen.getByRole('button', { name: 'copied' })).toBeInTheDocument();
  });

  it('covers editing, running activity, attached files, and stop states', () => {
    const p = props({
      isDark: true, running: true, editingIndex: 0, editingText: 'edit me',
      turns: [{ role: 'user', content: 'old' }, { role: 'assistant', content: '', steps: [] }],
      attachedImage: 'data:image/png;base64,x', attachedDocs: [{ name: 'long.txt', content: 'content', truncated: true }], imageError: 'bad image',
      dictationAvailable: true, listening: true,
    });
    const view = render(<AgentInterfaceView {...p} />);
    const editor = screen.getByRole('textbox', { name: 'saveAndResend' });
    Object.defineProperty(editor, 'scrollHeight', { configurable: true, value: 30 });
    fireEvent.change(editor, { target: { value: 'changed' } });
    fireEvent.keyDown(editor, { key: 'Enter' });
    fireEvent.keyDown(editor, { key: 'Escape' });
    fireEvent.click(screen.getByRole('button', { name: 'saveAndResend' }));
    fireEvent.click(screen.getByRole('button', { name: 'cancel' }));
    fireEvent.click(screen.getByRole('button', { name: 'agentRemoveImage' }));
    fireEvent.click(screen.getByRole('button', { name: 'removeDocument' }));
    fireEvent.click(screen.getByRole('button', { name: 'agentStop' }));
    expect(screen.getByRole('alert')).toHaveTextContent('bad image');
    expect(p.saveEdit).toHaveBeenCalledTimes(2);
    expect(p.cancelEdit).toHaveBeenCalledTimes(2);
    expect(p.setAttachedImage).toHaveBeenCalledWith(null);
    expect(p.setImageError).toHaveBeenCalledWith('');
    expect(p.setAttachedDocs).toHaveBeenCalled();
    expect(p.stop).toHaveBeenCalled();

    view.rerender(<AgentInterfaceView {...p} agentActivity="working" analyzingImage />);
    expect(screen.getByRole('status')).toHaveTextContent('agentAnalyzingImage');
  });
});
