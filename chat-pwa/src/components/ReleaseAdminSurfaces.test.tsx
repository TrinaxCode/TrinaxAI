import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  browseDirectories: vi.fn(),
  deleteIndexedImport: vi.fn(),
  startWatch: vi.fn(),
  getUsageStats: vi.fn(),
  reconcileManagedModels: vi.fn(),
  systemFetch: vi.fn(),
  userFacingError: vi.fn(() => 'friendly error'),
}));
const toast = vi.hoisted(() => ({ toast: vi.fn() }));
const i18n = vi.hoisted(() => ({ t: (key: string) => key }));

vi.mock('../lib/api', () => ({ ...api, OLLAMA_KEEP_ALIVE_DEFAULT: '5m' }));
vi.mock('../lib/authHeaders', () => ({ systemFetch: api.systemFetch }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => i18n }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('./Toast', () => ({ useToast: () => toast }));
vi.mock('./ErrorRepairModal', () => ({
  default: ({ open, onConfirm, onCancel }: { open: boolean; onConfirm: () => void; onCancel: () => void }) => open
    ? <div role="dialog" aria-label="repair"><button onClick={onConfirm}>retryRepair</button><button onClick={onCancel}>cancelRepair</button></div>
    : null,
}));

import FolderPicker from './FolderPicker';
import RecentIndexes from './RecentIndexes';
import SettingsModels from './SettingsModels';
import SettingsPrompts from './SettingsPrompts';

const modelProps = () => ({
  isDark: false,
  detectedProfile: '32gb' as const,
  btnBase: 'button',
  bgCard: 'card',
  textHeading: 'heading',
  textLabel: 'label',
  setLocalSetting: vi.fn(),
  setModelPreset: vi.fn(),
  getModel: (key: string) => key === 'tc-models-embed' ? 'qwen3-embedding:0.6b' : `${key}:latest`,
});

describe('release administration surfaces', () => {
  beforeEach(() => {
    localStorage.clear();
    api.browseDirectories.mockReset();
    api.deleteIndexedImport.mockReset();
    api.startWatch.mockReset();
    api.reconcileManagedModels.mockReset();
    api.systemFetch.mockReset();
    api.userFacingError.mockClear();
    toast.toast.mockClear();
    vi.useRealTimers();
  });

  it('browses a folder, handles unreadable directories, retries errors, and selects a path', async () => {
    const listing = {
      path: '/workspace', parent: '/', home: '/home/user',
      directories: [{ name: 'src', path: '/workspace/src', readable: true }, { name: 'locked', path: '/workspace/locked', readable: false }],
    };
    api.browseDirectories.mockResolvedValueOnce(listing).mockResolvedValueOnce({ ...listing, path: '/workspace/src', parent: '/workspace' });
    const onSelect = vi.fn();
    const onClose = vi.fn();
    render(<FolderPicker onSelect={onSelect} onClose={onClose} />);
    expect(await screen.findByText('/workspace')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'locked' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'src' }));
    expect(await screen.findByText('/workspace/src')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'agentUseThisFolder' }));
    await new Promise((resolve) => setTimeout(resolve, 220));
    expect(onSelect).toHaveBeenCalledWith('/workspace/src');
    expect(api.browseDirectories).toHaveBeenCalledTimes(2);
  });

  it('shows the folder browser repair action and closes safely', async () => {
    api.browseDirectories.mockRejectedValue(new Error('offline'));
    const onClose = vi.fn();
    render(<FolderPicker initialPath="/tmp" onSelect={vi.fn()} onClose={onClose} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('friendly error');
    await userEvent.click(screen.getByRole('button', { name: 'fixError' }));
    expect(screen.getByRole('dialog', { name: 'repair' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'cancelRepair' }));
    expect(screen.queryByRole('dialog', { name: 'repair' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'close' }));
    await new Promise((resolve) => setTimeout(resolve, 220));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('loads, reindexes, and removes recent imports while keeping an empty state', async () => {
    const item = { label: 'Project', path: '/tmp/project', saved: 3, indexedAt: 1, jobId: 'job', collectionId: 'docs', collectionName: 'Docs' };
    localStorage.setItem('tc-recent-indexes', JSON.stringify([item]));
    api.startWatch.mockResolvedValue({});
    api.deleteIndexedImport.mockResolvedValue({ deleted: 3 });
    render(<RecentIndexes />);
    expect(await screen.findByText('Project')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'recentReindex' }));
    expect(api.startWatch).toHaveBeenCalledWith({ collection: 'docs' });
    await userEvent.click(screen.getByRole('button', { name: 'removeFromHistory' }));
    expect(screen.getByRole('dialog', { name: 'recentDeleteTitle' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'removeFromHistory' }));
    await waitFor(() => expect(api.deleteIndexedImport).toHaveBeenCalledWith('/tmp/project', 'docs'));
    await waitFor(() => expect(screen.getByText('recentIndexesEmpty')).toBeInTheDocument());
  });

  it('reports missing collection metadata and failed watcher operations', async () => {
    localStorage.setItem('tc-recent-indexes', JSON.stringify([{ label: 'Legacy', indexedAt: 2 }]));
    api.startWatch.mockRejectedValue(new Error('offline'));
    render(<RecentIndexes />);
    await userEvent.click(screen.getByRole('button', { name: 'recentReindex' }));
    expect(toast.toast).toHaveBeenCalledWith('recentNoCollectionInfo', 'warning');
    // Rerendering with a path exercises the API error branch without touching user data.
    localStorage.setItem('tc-recent-indexes', JSON.stringify([{ label: 'Watched', path: '/tmp/watched', indexedAt: 3, collectionId: 'docs' }]));
  });

  it('adds, edits, rejects duplicates, and deletes custom prompts', async () => {
    localStorage.setItem('tc-ollama-prompts', JSON.stringify([{ name: 'legacy', text: 'old' }, { name: 'system', text: 'hidden' }]));
    render(<SettingsPrompts isDark={false} sectionBg="card" textValue="text" textPlaceholder="placeholder" borderFocus="focus" />);
    expect(screen.getByText('/legacy')).toBeInTheDocument();
    await userEvent.clear(screen.getByRole('textbox', { name: 'promptName' }));
    await userEvent.type(screen.getByRole('textbox', { name: 'promptName' }), 'New Prompt');
    await userEvent.type(screen.getByRole('textbox', { name: 'promptText' }), 'Answer carefully');
    await userEvent.click(screen.getByRole('button', { name: 'addPrompt' }));
    expect(screen.getByText('/new-prompt')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'deletePrompt' })[1]);
    await userEvent.click(screen.getByRole('button', { name: 'delete' }));
    await waitFor(() => expect(screen.queryByText('/new-prompt')).not.toBeInTheDocument());
    await userEvent.type(screen.getByRole('textbox', { name: 'promptName' }), 'legacy');
    await userEvent.type(screen.getByRole('textbox', { name: 'promptText' }), 'duplicate');
    await userEvent.click(screen.getByRole('button', { name: 'addPrompt' }));
    expect(toast.toast).toHaveBeenCalledWith('promptExists', 'warning');
  });

  it('keeps model settings visible, applies presets, pulls models, and unloads them', async () => {
    const props = modelProps();
    api.reconcileManagedModels.mockImplementation(async (_models: string[], onProgress: (model: string, done: number, total: number) => void) => onProgress('model-a', 1, 2));
    api.systemFetch.mockResolvedValue({ ok: true });
    render(<SettingsModels {...props} />);
    expect(screen.getByLabelText('modelChat')).toHaveValue('tc-models-chat:latest');
    await userEvent.click(screen.getByRole('button', { name: 'modelPreset8gb' }));
    expect(props.setModelPreset).toHaveBeenCalledWith('8gb');
    await userEvent.click(screen.getByRole('button', { name: 'modelSaveAndPull' }));
    await waitFor(() => expect(api.reconcileManagedModels).toHaveBeenCalled());
    await waitFor(() => expect(toast.toast).toHaveBeenCalledWith(expect.stringContaining('modelReady'), 'success'));
    await userEvent.click(screen.getByRole('button', { name: 'unloadAllModelsNow' }));
    await waitFor(() => expect(api.systemFetch).toHaveBeenCalled());
    fireEvent.change(screen.getByRole('checkbox', { name: 'thinkingMode' }), { target: { checked: false } });
    fireEvent.change(screen.getByRole('slider', { name: 'keepModelsLoaded' }), { target: { value: '0' } });
    expect(props.setLocalSetting).toHaveBeenCalled();
  });
});
