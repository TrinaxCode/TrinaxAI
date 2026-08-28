import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import NetworkNotice from './NetworkNotice';

const systemFetch = vi.fn();
const wipeRevokedDeviceData = vi.fn();
vi.mock('../lib/authHeaders', () => ({ systemFetch: (...args: unknown[]) => systemFetch(...args) }));
vi.mock('../lib/deviceWipe', () => ({ wipeRevokedDeviceData: () => wipeRevokedDeviceData() }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));

const network = {
  online: true,
  recommendedUrl: 'https://trinaxai.local:3334',
  urls: ['https://trinaxai.local:3334', 'https://192.168.0.18:3334'],
  needsRefresh: true,
  refreshCommand: 'trinaxai network refresh',
};

describe('NetworkNotice', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    systemFetch.mockReset();
    wipeRevokedDeviceData.mockReset();
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('stays hidden while the current network configuration is valid', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ ...network, needsRefresh: false }), { status: 200 }));
    render(<NetworkNotice canManageSystem />);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/network', expect.objectContaining({ cache: 'no-store' })));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows the offline notice when the network drops after a healthy check', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ ...network, needsRefresh: false }), { status: 200 }));
    render(<NetworkNotice canManageSystem />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());

    fireEvent(window, new Event('offline'));

    expect(await screen.findByText('networkOfflineTitle')).toBeInTheDocument();
  });

  it('refreshes a changed network and presents the stable link', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(network), { status: 200 }));
    systemFetch.mockResolvedValue(new Response(JSON.stringify({ ok: true, ...network }), { status: 200 }));
    render(<NetworkNotice canManageSystem />);
    await userEvent.click(await screen.findByRole('button', { name: 'networkPrepare' }));
    expect(systemFetch).toHaveBeenCalledWith('/api/system/network-refresh', { method: 'POST' });
    expect(await screen.findByRole('link', { name: 'networkOpenNewLink' })).toHaveAttribute('href', network.recommendedUrl);
  });

  it('identifies a cached offline shell and provides the host command', async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError('offline'));
    render(<NetworkNotice canManageSystem={false} />);
    expect(await screen.findByText('networkOfflineTitle')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'networkCopyCommand' }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('trinaxai network refresh');
  });

  it('stays dismissed for the same network but returns when the addresses change', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(network), { status: 200 }));
    const { unmount } = render(<NetworkNotice canManageSystem />);
    await userEvent.click(await screen.findByRole('button', { name: 'close' }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    unmount();

    render(<NetworkNotice canManageSystem />);
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());

    vi.mocked(fetch).mockResolvedValue(new Response(
      JSON.stringify({ ...network, urls: ['https://192.168.1.42:3334'] }),
      { status: 200 },
    ));
    render(<NetworkNotice canManageSystem />);
    expect(await screen.findByText('networkChangedTitle')).toBeInTheDocument();
  });

  it('removes an old offline origin only after explicit confirmation', async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError('offline'));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    wipeRevokedDeviceData.mockReturnValue(new Promise(() => undefined));
    render(<NetworkNotice canManageSystem={false} />);
    await userEvent.click(await screen.findByRole('button', { name: 'networkRemoveOld' }));
    expect(window.confirm).toHaveBeenCalledWith('networkRemoveOldConfirm');
    expect(wipeRevokedDeviceData).toHaveBeenCalledOnce();
  });
});
