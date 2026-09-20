import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Settings from './Settings';
import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import { ToastProvider } from './Toast';

const mocks = vi.hoisted(() => ({ getIndexJob: vi.fn() }));

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
  getIndexJob: mocks.getIndexJob,
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

const runningJob = {
  id: 'job-1',
  label: 'Docs',
  path: '/docs',
  status: 'indexing',
  phase: 'embedding',
  progress: 74,
  eta_seconds: 125,
  elapsed_seconds: 97,
  saved: 40,
  skipped: 0,
  bytes: 0,
  indexed: false,
  projects: [],
  collection_id: 'default',
  collection_name: 'General',
  pages_total: null,
  pages_processed: 0,
  files_total: 40,
  files_processed: 40,
  chunks_generated: 143,
  batches_total: 5,
  batches_processed: 2,
  progress_exact: false,
  recent_activity: '🔨 Embeddings lote 3/5...',
  failures: [],
  retry_recommended: false,
};

function renderIndexingTab() {
  return render(
    <ThemeProvider>
      <I18nProvider>
        <ToastProvider>
          <Settings onBack={vi.fn()} onOpenDocs={vi.fn()} initialSection="indexing" canManageSystem />
        </ToastProvider>
      </I18nProvider>
    </ThemeProvider>,
  );
}

describe('indexing progress bar', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('tc-last-index-import', JSON.stringify({ jobId: 'job-1' }));
    mocks.getIndexJob.mockReset();
    mocks.getIndexJob.mockResolvedValue(runningJob);
  });

  it('shows the percentage from the real counters with duration metrics', async () => {
    renderIndexingTab();

    const bar = await screen.findByRole('progressbar');
    expect(bar).toHaveClass('tc-index-track');
    expect(bar).toHaveAttribute('aria-valuenow', '74');
    expect(bar).toHaveAttribute('aria-valuemax', '100');

    expect(screen.getByText('74%')).toBeInTheDocument();
    // 97s elapsed and a 2m 05s estimate, both formatted from real seconds.
    expect(screen.getByText('1m 37s')).toBeInTheDocument();
    expect(screen.getByText('~2m 05s')).toBeInTheDocument();
    expect(screen.getByText('143')).toBeInTheDocument();
  });

  it('marks an estimated percentage and animates the bar while a batch is in flight', async () => {
    const { container } = renderIndexingTab();

    await screen.findByRole('progressbar');
    const fill = container.querySelector('.tc-index-fill');
    expect(fill).toHaveClass('tc-index-fill--live');
    expect(fill).toHaveStyle({ width: '74%' });
    expect(screen.getByText(/aprox|approx/i)).toBeInTheDocument();
  });

  it('drops the estimate marker once the indexer reports exact counters', async () => {
    mocks.getIndexJob.mockResolvedValue({ ...runningJob, phase: 'chunking', progress_exact: true });
    const { container } = renderIndexingTab();

    await screen.findByRole('progressbar');
    expect(container.querySelector('.tc-index-fill--live')).toBeNull();
    expect(screen.queryByText(/aprox|approx/i)).toBeNull();
  });
});
