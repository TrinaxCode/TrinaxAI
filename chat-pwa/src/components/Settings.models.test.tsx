import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Settings from './Settings';
import { deleteCollectionSources, getCollections, resetSharedAppState } from '../lib/api';
import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import { ToastProvider } from './Toast';
import { expectNoA11yViolations } from '../test/a11y';

vi.mock('../lib/api', () => ({
  apiErrorFromPayload: vi.fn(),
  DEFAULT_MODEL_SETTINGS: {
    chat: 'qwen3.5:4b',
    deep: 'qwen3.5:4b',
    vision: 'qwen3.5:4b',
    embed: 'qwen3-embedding:0.6b',
    code: 'qwen3.5:4b',
    fast: 'qwen3.5:2b',
  },
  MODEL_KEYS: ['chat', 'deep', 'vision', 'embed', 'code', 'fast'],
  MODEL_PRESETS: { '8gb': {}, '16gb': {}, '32gb': {}, '64gb': {} },
  checkStatus: vi.fn().mockResolvedValue({ profile: '16gb' }),
  OLLAMA_KEEP_ALIVE_DEFAULT: '0s',
  cancelIndexJob: vi.fn(),
  createCollection: vi.fn(),
  deleteCollection: vi.fn(),
  deleteCollectionSources: vi.fn(),
  folderLabelFromFiles: vi.fn(() => 'folder'),
  getCollections: vi.fn().mockResolvedValue([]),
  getIndexJob: vi.fn(),
  indexableFilesFrom: vi.fn((files: File[]) => files),
  modelSetting: vi.fn((_key: string, fallback: string) => fallback),
  reconcileManagedModels: vi.fn(),
  renameCollection: vi.fn(),
  resetSharedAppState: vi.fn(),
  retryIndexJob: vi.fn(),
  startFolderIndex: vi.fn(),
  startLocalAi: vi.fn(),
  systemRequestHeaders: vi.fn(() => new Headers()),
  formatUserFacingError: vi.fn(() => 'Error'),
  userFacingError: vi.fn(() => 'Error'),
}));

vi.mock('./StatusDots', () => ({ default: () => <div data-testid="status-dots" /> }));
vi.mock('./WatcherCard', () => ({ default: () => <div data-testid="watcher-card" /> }));
vi.mock('./MemoryPanel', () => ({ default: () => <div data-testid="memory-panel" /> }));
vi.mock('./FolderPicker', () => ({ default: () => <div data-testid="folder-picker" /> }));
vi.mock('./DevicePairingCard', () => ({ default: () => <div data-testid="pairing-card" /> }));
vi.mock('./StatsPanel', () => ({ default: () => <div data-testid="stats-panel" /> }));
vi.mock('./RecentIndexes', () => ({ default: () => <div data-testid="recent-indexes" /> }));
vi.mock('./WebSearchSettings', () => ({ default: () => <div data-testid="web-search-settings" /> }));

function renderSettings() {
  return render(
    <ThemeProvider>
      <I18nProvider>
        <ToastProvider>
          <Settings onBack={vi.fn()} onOpenDocs={vi.fn()} canManageSystem />
        </ToastProvider>
      </I18nProvider>
    </ThemeProvider>,
  );
}

describe('Settings model guidance', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(resetSharedAppState).mockReset();
    vi.mocked(deleteCollectionSources).mockReset();
  });

  it('keeps canirun and the external model guide inside the model profile panel', async () => {
    const user = userEvent.setup();
    renderSettings();

    expect(screen.queryByText('Choose models with more context')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Models & profile/ }));

    expect(screen.getByText('Choose models with more context')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /canirun\.ai/ })).toHaveAttribute('href', 'https://www.canirun.ai');
    expect(screen.getByText('Ask another AI for recommendations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy guide' })).toBeInTheDocument();
    await expectNoA11yViolations(document.body);
  });

  it('keeps local state when the host rejects a factory reset', async () => {
    const user = userEvent.setup();
    localStorage.setItem('tc-theme', 'dark');
    vi.mocked(resetSharedAppState).mockRejectedValueOnce(new Error('localhost only'));
    renderSettings();

    await user.click(screen.getByRole('button', { name: 'Factory reset TrinaxAI' }));
    await user.type(screen.getByPlaceholderText('Type RESTORE to confirm:'), 'RESTORE');
    const resetButtons = screen.getAllByRole('button', { name: 'Factory reset TrinaxAI' });
    await user.click(resetButtons.at(-1)!);

    expect(resetSharedAppState).toHaveBeenCalledOnce();
    expect(localStorage.getItem('tc-theme')).toBe('dark');
  });

  it('clears indexed content from General without deleting the collection', async () => {
    vi.mocked(getCollections).mockResolvedValueOnce([
      { id: 'default', name: 'General', created_at: 1, updated_at: 1 },
    ]);
    vi.mocked(deleteCollectionSources).mockResolvedValueOnce({ deleted: 3, collection: 'default' });
    const user = userEvent.setup();
    renderSettings();

    await user.click(screen.getByRole('button', { name: 'Indexing' }));
    const clearButton = await screen.findByRole('button', { name: 'Clear collection content General' });
    await user.click(clearButton);
    await user.click(screen.getByRole('button', { name: 'Clear collection content' }));

    expect(deleteCollectionSources).toHaveBeenCalledWith('default');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});
