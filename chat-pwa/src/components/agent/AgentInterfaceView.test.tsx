import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
vi.mock('../chat/SpeakingIndicator', () => ({ default: ({ speaking }: any) => speaking ? <div role="status">speaking</div> : null }));
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
    modelNames: { chat: 'chat-model', deep: 'deep-model', fast: 'fast-model' }, sessionResetKey: 0,
    userDisplayName: 'Ada', ttsSupported: true, ttsActiveKey: null, ttsSpeaking: false, speak: callback(), stopSpeak: callback(),
    ...overrides,
  };
}

describe('AgentInterfaceView', () => {
  it('uses a black welcome orb in dark mode and a white one in light mode', () => {
    const p = props({ isDark: true });
    const view = render(<AgentInterfaceView {...p} />);
    expect(screen.getByRole('img', { name: 'TrinaxAI' }).parentElement).toHaveClass('bg-black');
    view.rerender(<AgentInterfaceView {...p} isDark={false} />);
    expect(screen.getByRole('img', { name: 'TrinaxAI' }).parentElement).toHaveClass('bg-white');
  });

  it('distinguishes no agent history from a search with no matches', () => {
    const p = props({ historyOpen: true });
    const view = render(<AgentInterfaceView {...p} />);
    expect(screen.getByText('agentNoHistory')).toBeInTheDocument();
    view.rerender(<AgentInterfaceView {...p} search="missing" />);
    expect(screen.getByText('noChatResults')).toBeInTheDocument();
  });

  it('delegates empty-state, header, workspace, mobile tools, and composer controls', () => {
    const p = props({ mobileToolsOpen: true, knowledgeSearch: true, webSearch: true, deepResearch: true, attachmentMenuOpen: true, dictationAvailable: true, input: 'ship it' });
    const view = render(<AgentInterfaceView {...p} />);
    const { container } = view;
    expect(container.querySelector('.agent-empty-state h2')).toBeVisible();
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveAttribute('src', '/logo-for-ai.webp');

    for (const name of ['back', 'agentHistory', 'agentNewSession', 'agentPickFolder', 'agentVoiceMode', 'agentSend']) {
      fireEvent.click(screen.getByRole('button', { name }));
    }
    fireEvent.click(container.querySelector('.agent-empty-state .chip-elegant')!);
    fireEvent.click(screen.getAllByRole('switch', { name: 'agentYoloModeOff' })[0]);
    expect(p.onBack).toHaveBeenCalled();
    expect(p.openHistory).toHaveBeenCalled();
    expect(p.startNewSession).toHaveBeenCalled();
    expect(p.setPickerOpen).toHaveBeenCalledWith(true);
    expect(p.setInput).toHaveBeenCalledWith(expect.stringMatching(/^quickChip.*Prompt$|^agentSuggestion.*Prompt$/));
    expect(p.handleYoloChange).toHaveBeenCalledWith(true);
    expect(p.toggleDictation).toHaveBeenCalled();
    expect(p.send).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'agentTools' }));
    fireEvent.click(screen.getAllByRole('button', { name: 'agentRagOn' })[1]);
    fireEvent.click(screen.getAllByRole('button', { name: 'agentWebSearchOn' })[1]);
    fireEvent.click(screen.getAllByRole('button', { name: 'agentDeepResearch' })[1]);
    fireEvent.click(screen.getByRole('radio', { name: /agentModelDeep/ }));
    expect(p.setKnowledgeSearch).toHaveBeenCalled();
    expect(p.setWebSearch).toHaveBeenCalled();
    expect(p.setDeepResearch).toHaveBeenCalled();
    expect(p.setModelMode).toHaveBeenCalledWith('deep');

    const workspace = screen.getByRole('textbox', { name: 'agentWorkspaceRootLabel' });
    expect(workspace).toHaveAttribute('placeholder', 'agentWorkspaceRootLabel');
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
    fireEvent.click(screen.getByRole('button', { name: 'delete agentUntitled' }));
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

  it('shows git commands with their own hint and a remote warning for push, pull and fetch', () => {
    const steps = [
      { id: 'g1', tool: 'git', dangerous: true, args: { args: "commit -m 'Fix parser'" }, status: 'awaiting' as const },
      { id: 'g2', tool: 'git', dangerous: true, args: { args: 'push origin main' }, status: 'awaiting' as const },
    ];
    render(<AgentInterfaceView {...props({ turns: [{ role: 'assistant' as const, content: '', steps }] })} />);

    expect(screen.getByText('toolGit')).toBeInTheDocument();
    expect(screen.getByText('toolGitRemote')).toBeInTheDocument();
    // Each call is shown in the step summary and in the approval preview.
    expect(screen.getAllByText(/git commit -m 'Fix parser'/)).toHaveLength(2);
    expect(screen.getAllByText(/git push origin main/)).toHaveLength(2);
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
    expect(screen.getByRole('status')).toHaveAccessibleName('agentAnalyzingImage');
  });

  it('renders turns with the same rows, avatars and bubbles as the chat', () => {
    const turns = [
      { role: 'user' as const, content: 'question' },
      { role: 'assistant' as const, content: 'answer', model: 'qwen' },
    ];
    const { container } = render(<AgentInterfaceView {...props({ turns })} />);
    expect(container.querySelectorAll('.chat-row')).toHaveLength(2);
    expect(container.querySelector('.chat-assistant-avatar')).toBeInTheDocument();
    expect(container.querySelector('.chat-bubble-assistant')).toHaveTextContent('answer');
    expect(screen.getByLabelText('userAvatar')).toHaveTextContent('A');
    expect(container.querySelector('.tc-agent-shell, .tc-agent-reply')).toBeNull();
    expect(container.querySelector('.chat-composer')).toHaveClass('max-w-[56rem]');
  });

  it('reads answers aloud and stops the active one', () => {
    const turns = [{ role: 'user' as const, content: 'q' }, { role: 'assistant' as const, content: 'spoken answer' }];
    const p = props({ turns });
    const view = render(<AgentInterfaceView {...p} />);
    fireEvent.click(screen.getByRole('button', { name: 'listen' }));
    expect(p.speak).toHaveBeenCalledWith('spoken answer', 'agent-msg-1');

    view.rerender(<AgentInterfaceView {...p} ttsActiveKey="agent-msg-1" ttsSpeaking />);
    expect(screen.getByRole('status')).toHaveTextContent('speaking');
    fireEvent.click(screen.getByRole('button', { name: 'stop' }));
    expect(p.stopSpeak).toHaveBeenCalled();

    view.rerender(<AgentInterfaceView {...p} ttsSupported={false} />);
    expect(screen.queryByRole('button', { name: 'listen' })).toBeNull();
  });

  it('shows YOLO as an explicit switch with a visible active state', () => {
    const p = props({ yoloMode: true });
    const { container } = render(<AgentInterfaceView {...p} />);
    const toggle = screen.getByRole('switch', { name: 'agentYoloModeOn' });
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    expect(toggle).toHaveAttribute('data-enabled', 'true');
    expect(container.querySelector('nav')).toHaveAttribute('data-yolo', 'on');
    expect(screen.getByText('agentYoloActiveBanner')).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(p.handleYoloChange).toHaveBeenCalledWith(false);
  });

  it('lets the user pick the agent model from a popover that names the model behind each mode', async () => {
    const p = props({ turns: [{ role: 'assistant', content: 'done', model: 'qwen3.5:4b' }] });
    render(<AgentInterfaceView {...p} />);
    const trigger = screen.getByRole('button', { name: 'agentModel: agentModelAuto' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveTextContent('qwen3.5:4b');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const dialog = screen.getByRole('dialog', { name: 'agentModel' });
    expect(within(dialog).getByRole('radio', { name: /agentModelAuto/ })).toBeChecked();
    expect(within(dialog).getByText('deep-model')).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('radio', { name: /agentModelFast/ }));
    expect(p.setModelMode).toHaveBeenCalledWith('fast');
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'agentModel' })).toBeNull());
  });

  it('gives the agent history the same surface and new-session action as the chat sidebar', () => {
    const p = props({ isDark: true, historyOpen: true });
    render(<AgentInterfaceView {...p} />);
    const drawer = screen.getByRole('dialog', { name: 'agentHistory' });
    expect(drawer).toHaveClass('sidebar-surface', 'bg-black/65', 'border-white/[0.06]');
    fireEvent.click(within(drawer).getByRole('button', { name: 'agentNewSession' }));
    expect(p.startNewSession).toHaveBeenCalled();
  });
});
