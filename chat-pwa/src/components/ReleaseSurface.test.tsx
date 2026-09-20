import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getUsageStats: vi.fn(),
  checkStatus: vi.fn(),
}));
const shared = vi.hoisted(() => ({ onSharedStateUpdated: vi.fn(() => () => undefined) }));
const toast = vi.hoisted(() => ({ toast: vi.fn() }));
const i18n = vi.hoisted(() => ({ t: (key: string) => key }));

vi.mock('../lib/api', () => ({
  getUsageStats: api.getUsageStats,
  checkStatus: api.checkStatus,
  userFacingError: () => 'friendly error',
}));
vi.mock('../lib/sharedState', () => shared);
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => i18n }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('./Toast', () => ({ useToast: () => toast }));

import PermissionNotice from './PermissionNotice';
import PwaUpdater from './PwaUpdater';
import StatsPanel from './StatsPanel';
import StatusDots from './StatusDots';

describe('release-facing status surfaces', () => {
  beforeEach(() => {
    api.getUsageStats.mockReset();
    api.checkStatus.mockReset();
    shared.onSharedStateUpdated.mockClear();
    toast.toast.mockClear();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  });

  it.each([
    ['rag', 'permissionFeature_rag'],
    ['knowledge', 'permissionFeature_knowledge'],
    ['memory', 'permissionFeature_memory'],
    ['stats', 'permissionFeature_stats'],
    ['index', 'permissionFeature_index'],
    ['agent', 'permissionFeature_agent'],
  ] as const)('renders the protected %s message and returns to the previous page', async (feature, copy) => {
    const onBack = vi.fn();
    render(<PermissionNotice feature={feature} onBack={onBack} />);
    expect(screen.getByText(copy)).toBeInTheDocument();
    expect(screen.getByText(feature === 'index' || feature === 'agent' ? 'permissionHostOnly' : 'permissionTutorial')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button'));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('renders the remote web-search notice without the private permission tutorial', () => {
    render(<PermissionNotice feature="web" remoteWebSearch onBack={vi.fn()} />);
    expect(screen.getByText('remoteWebSearchNoticeTitle')).toBeInTheDocument();
    expect(screen.queryByText('permissionTutorial')).not.toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveTextContent('remoteWebSearchNoticeButton');
  });

  it('refreshes or dismisses the PWA update banner and resurfaces a newer update', async () => {
    const onRefresh = vi.fn();
    const { rerender } = render(<PwaUpdater needsUpdate={false} onRefresh={onRefresh} />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    rerender(<PwaUpdater needsUpdate onRefresh={onRefresh} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'pwaUpdate' }));
    expect(onRefresh).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole('button', { name: 'close' }));
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
    rerender(<PwaUpdater needsUpdate={false} onRefresh={onRefresh} />);
    rerender(<PwaUpdater needsUpdate onRefresh={onRefresh} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows stats, formats large values, and refreshes on demand', async () => {
    api.getUsageStats.mockResolvedValue({
      messages_total: 1_250,
      tokens_estimated: 2_000_000,
      first_seen: 1_700_000_000,
      last_seen: 1_700_000_100,
      top_models: [{ model: 'model-a', count: 100 }],
      top_collections: [{ id: 'docs', count: 50 }],
      messages_by_engine: { ollama: 100 },
    });
    render(<StatsPanel />);
    expect(await screen.findByText('1.3k')).toBeInTheDocument();
    expect(screen.getByText('2.0M')).toBeInTheDocument();
    expect(screen.getByText('model-a')).toBeInTheDocument();
    expect(screen.getByText('docs')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    expect(api.getUsageStats).toHaveBeenCalledTimes(2);
  });

  it('shows an offline stats state and reports the failure once', async () => {
    api.getUsageStats.mockRejectedValue(new Error('offline'));
    render(<StatsPanel />);
    expect(await screen.findByText('statsUnavailableOffline')).toBeInTheDocument();
    expect(toast.toast).toHaveBeenCalledWith('friendly error', 'error');
    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(api.getUsageStats).toHaveBeenCalledTimes(2));
    expect(toast.toast).toHaveBeenCalledTimes(1);
  });

  it('renders status dots for healthy, indexed, and partial states and refreshes on focus', async () => {
    api.checkStatus.mockResolvedValue({ ollama: true, rag: true, indexed: false, ramPercent: 42.4, profile: '16gb' });
    render(<StatusDots />);
    await waitFor(() => expect(api.checkStatus).toHaveBeenCalledOnce());
    expect(screen.getByText('ollamaStatus')).toBeInTheDocument();
    expect(screen.getByText('ragStatus')).toBeInTheDocument();
    expect(screen.getByText('RAM 42%')).toBeInTheDocument();
    expect(screen.getByText('hardwareProfile: 16gb')).toBeInTheDocument();
    fireEvent.focus(window);
    await waitFor(() => expect(api.checkStatus).toHaveBeenCalledTimes(2));
    expect(shared.onSharedStateUpdated).toHaveBeenCalledOnce();
  });
});
