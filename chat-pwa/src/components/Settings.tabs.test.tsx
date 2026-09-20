import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import Settings from './Settings';
import { APP_CONFIG } from '../lib/config';
import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import { ToastProvider } from './Toast';

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

function renderSettings(overrides: Partial<React.ComponentProps<typeof Settings>> = {}) {
  return render(
    <ThemeProvider>
      <I18nProvider>
        <ToastProvider>
          <Settings onBack={vi.fn()} onOpenDocs={vi.fn()} canManageSystem {...overrides} />
        </ToastProvider>
      </I18nProvider>
    </ThemeProvider>,
  );
}

describe('Settings section tabs', () => {
  it('exposes every section as a tab with a single accessible current marker', async () => {
    const user = userEvent.setup();
    const { container } = renderSettings();

    const tabs = [...container.querySelectorAll('.page-tabs button')];
    expect(tabs).toHaveLength(8);
    expect(tabs.filter((tab) => tab.getAttribute('aria-current') === 'page')).toHaveLength(1);

    const webSearchTab = screen.getByRole('button', { name: /web search|búsqueda/i });
    await user.click(webSearchTab);

    expect(webSearchTab).toHaveAttribute('aria-current', 'page');
    expect(tabs.filter((tab) => tab.getAttribute('aria-current') === 'page')).toHaveLength(1);
    expect(container.querySelector('[data-testid="web-search-settings"]')).not.toBeNull();
  });

  it('moves between sections with the arrow keys', async () => {
    const user = userEvent.setup();
    renderSettings();

    const generalTab = screen.getByRole('button', { name: /general/i });
    generalTab.focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByRole('button', { name: /web search|búsqueda/i })).toHaveAttribute('aria-current', 'page');
  });

  it('keeps the only GitHub link in the header pointing at the TrinaxAI repository', () => {
    const { container } = renderSettings();

    const githubLinks = [...container.querySelectorAll('a[href*="github.com"]')];
    expect(githubLinks).toHaveLength(1);
    expect(githubLinks[0]).toHaveAttribute('href', APP_CONFIG.repoUrl);
  });

  it('covers read-only profile/preferences and external section jumps', async () => {
    const user = userEvent.setup();
    renderSettings({ canManageSystem: false });

    expect(screen.queryByRole('button', { name: /shutdown|apagar/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /edit|editar/i }));
    const nickname = screen.getByRole('textbox', { name: /nickname|nombre/i });
    await user.type(nickname, 'Ana');
    await user.click(screen.getByRole('button', { name: /save|guardar/i }));
    await user.click(screen.getByRole('switch', { name: /sound effects|efectos de sonido/i }));
    await user.click(screen.getByRole('switch', { name: /sound effects|efectos de sonido/i }));

    const language = screen.getByRole('button', { name: /English|Español|Spanish/i });
    await user.click(language);
    await user.click(screen.getByRole('button', { name: /dark mode|light mode|modo oscuro|modo claro|oscuro|claro/i }));
    await user.click(screen.getByRole('button', { name: /advanced|avanzado/i }));
    expect(screen.getByRole('note')).toHaveTextContent(/paired devices cannot administer|dispositivos vinculados no pueden administrar/i);
    expect(screen.queryByRole('button', { name: /unlock|desbloquear/i })).not.toBeInTheDocument();
    window.dispatchEvent(new CustomEvent('tc-open-section', { detail: { section: 'help' } }));
    expect(await screen.findByText(/open source|código abierto/i)).toBeInTheDocument();
    window.dispatchEvent(new CustomEvent('tc-open-section', { detail: { section: 'invalid' } }));
    window.dispatchEvent(new Event('tc-open-memory-tab'));
    expect(await screen.findByTestId('memory-panel')).toBeInTheDocument();
  });

  it('runs system confirmations and the restore cancel branch', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({ status: 200, json: async () => ({ ok: true }) });
    vi.stubGlobal('fetch', fetchMock);
    renderSettings();

    await user.click(screen.getByRole('button', { name: /advanced|avanzado/i }));
    expect(screen.getByText(/danger zone|zona de riesgo/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /shutdown|apagar/i }));
    const shutdown = screen.getByRole('dialog', { name: /shutdown|apagar/i });
    await user.click(within(shutdown).getByRole('button', { name: /cancel|cancelar/i }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /shutdown|apagar/i })).not.toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /shutdown|apagar/i }));
    await user.click(within(screen.getByRole('dialog', { name: /shutdown|apagar/i })).getByRole('button', { name: /shutdown|apagar/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    await user.click(screen.getByRole('button', { name: /startup|encender/i }));
    const startup = screen.getByRole('dialog', { name: /startup|encender/i });
    await user.click(within(startup).getByRole('button', { name: /startup|encender/i }));
    const restoreTriggers = screen.getAllByRole('button', { name: /restore|restaurar|factory reset/i });
    expect(restoreTriggers.at(-1)).toBeInTheDocument();
    await user.click(restoreTriggers.at(-1)!);
    const restoreInput = screen.getByRole('textbox', { name: /RESTORE|RESTAURAR/i });
    await user.type(restoreInput, 'WRONG');
    expect(screen.getAllByRole('button', { name: /restore|restaurar|factory reset/i }).at(-1)).toBeDisabled();
    await user.click(screen.getAllByRole('button', { name: /cancel|cancelar/i }).at(-1)!);
    await user.click(screen.getByRole('button', { name: /stop all|detener.*todo/i }));
    const stopAll = screen.getByRole('dialog', { name: /shut down|apagar completamente/i });
    const stopConfirm = within(stopAll).getByRole('button', { name: /stop all|detener.*todo/i });
    expect(stopConfirm).toBeDisabled();
    const stopInput = within(stopAll).getByRole('textbox');
    await user.type(stopInput, stopInput.getAttribute('placeholder') || 'STOP ALL');
    expect(stopConfirm).not.toBeDisabled();
    await user.click(stopConfirm);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/system/stop-all', expect.anything()));
    vi.unstubAllGlobals();
  });
});
