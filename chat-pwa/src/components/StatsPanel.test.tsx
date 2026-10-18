import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import StatsPanel from './StatsPanel';

const mocks = vi.hoisted(() => ({
  getUsageStats: vi.fn(),
  toastApi: { toast: vi.fn() },
  t: (key: string) => key,
  isDark: false,
}));

vi.mock('../lib/api', () => ({
  getUsageStats: mocks.getUsageStats,
  userFacingError: () => 'Statistics are temporarily unavailable',
}));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: mocks.t }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: mocks.isDark }) }));
vi.mock('./Toast', () => ({ useToast: () => mocks.toastApi }));

it('keeps the actual statistics error visible after a failed load', async () => {
  mocks.getUsageStats.mockRejectedValue(new Error('request failed'));

  render(<StatsPanel />);

  expect(await screen.findByRole('status')).toHaveTextContent('Statistics are temporarily unavailable');
  expect(screen.getByRole('button', { name: 'refresh' })).toBeEnabled();
});

it('shows usage totals and breakdowns after a successful load', async () => {
  mocks.isDark = true;
  mocks.getUsageStats.mockResolvedValue({
    messages_total: 1500,
    messages_by_engine: { rag: 900 },
    tokens_estimated: 2500,
    top_collections: [{ id: 'docs', count: 600 }],
    top_models: [{ model: 'qwen', count: 1200 }],
    index_runs: 2,
    first_seen: 1,
    last_seen: 2,
  });

  render(<StatsPanel />);

  expect(await screen.findByText('1.5k')).toBeInTheDocument();
  expect(screen.getByText('2.5k')).toBeInTheDocument();
  expect(screen.getByText('qwen')).toBeInTheDocument();
  expect(screen.getByText('docs')).toBeInTheDocument();
  expect(screen.getByText('rag')).toBeInTheDocument();
  expect(screen.getByText('usageStatsTitle')).toHaveClass('text-white/80');
  mocks.isDark = false;
});
