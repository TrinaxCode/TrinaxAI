import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WebSearchSettings from './WebSearchSettings';

const get = vi.fn(); const save = vi.fn(); const test = vi.fn(); const remove = vi.fn(); const reset = vi.fn();
vi.mock('../lib/api', () => ({
  getWebSearchSettings: (...args: unknown[]) => get(...args),
  saveWebSearchSettings: (...args: unknown[]) => save(...args),
  testWebSearchProvider: (...args: unknown[]) => test(...args),
  deleteWebSearchCredential: (...args: unknown[]) => remove(...args),
  resetWebSearchSettings: (...args: unknown[]) => reset(...args),
}));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ lang: 'en' }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));

const state = {
  enabled: true, preferred_provider: 'duckduckgo', active_provider: 'duckduckgo', source: 'default',
  externally_managed: { preferred_provider: false, brave_api_key: false, searxng_url: false },
  providers: {
    duckduckgo: { available: true, configured: true, requires_api_key: false },
    brave: { available: true, configured: false, requires_api_key: true },
    searxng: { available: true, configured: false, requires_api_key: false, base_url: null },
  },
};

describe('WebSearchSettings', () => {
  beforeEach(() => { vi.clearAllMocks(); get.mockResolvedValue(state); save.mockResolvedValue(state); reset.mockResolvedValue(state); });

  it('renders real providers and never loads an existing secret', async () => {
    render(<WebSearchSettings canManageSystem />);
    const select = await screen.findByLabelText('Preferred search engine');
    expect(select).toHaveValue('duckduckgo');
    await userEvent.selectOptions(select, 'brave');
    const secret = screen.getByLabelText(/Brave Search API key/);
    expect(secret).toHaveAttribute('type', 'password');
    expect(secret).toHaveValue('');
  });

  it('saves the selected provider and tests it from the backend', async () => {
    test.mockResolvedValue({ ok: true, provider: 'duckduckgo', result_count: 1 });
    render(<WebSearchSettings canManageSystem />);
    await screen.findByText('Web search');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({ preferred_provider: 'duckduckgo' })));
    await userEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    expect(await screen.findByText('Connection successful: duckduckgo')).toBeInTheDocument();
  });

  it('blocks the form without system scope', () => {
    render(<WebSearchSettings canManageSystem={false} />);
    expect(screen.getByRole('alert')).toHaveTextContent('system permission');
  });

  it('aborts the connection test when saving changed credentials fails', async () => {
    save.mockRejectedValue(new Error('Save failed'));
    render(<WebSearchSettings canManageSystem />);
    await userEvent.selectOptions(await screen.findByLabelText('Preferred search engine'), 'brave');
    await userEvent.type(screen.getByLabelText(/Brave Search API key/), 'new-secret');
    await userEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    expect(await screen.findByText('Save failed')).toBeInTheDocument();
    expect(test).not.toHaveBeenCalled();
  });

  it('locks only fields managed by the environment', async () => {
    get.mockResolvedValue({
      ...state,
      externally_managed: { preferred_provider: false, brave_api_key: true, searxng_url: false },
    });
    render(<WebSearchSettings canManageSystem />);
    const select = await screen.findByLabelText('Preferred search engine');
    expect(select).toBeEnabled();
    await userEvent.selectOptions(select, 'brave');
    expect(screen.getByLabelText(/Brave Search API key/)).toBeDisabled();
  });

  it('surfaces reset failures', async () => {
    reset.mockRejectedValue(new Error('Reset failed'));
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true);
    render(<WebSearchSettings canManageSystem />);
    await screen.findByText('Web search');
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(await screen.findByText('Reset failed')).toBeInTheDocument();
  });
});
