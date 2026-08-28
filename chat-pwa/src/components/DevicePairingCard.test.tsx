import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DevicePairingCard from './DevicePairingCard';
import { claimDevice, getCurrentPairedDevice, listPairedDevices, revokeCurrentPairedDevice } from '../lib/devicePairing';

vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
vi.mock('../lib/devicePairing', () => ({
  claimDevice: vi.fn(),
  getCurrentPairedDevice: vi.fn(),
  listPairedDevices: vi.fn(),
  revokeCurrentPairedDevice: vi.fn(),
}));

const device = {
  id: '0123456789abcdef01234567',
  name: 'Kitchen tablet',
  scopes: ['chat', 'read_private'],
  created_at: 1,
  last_seen_at: null,
  expires_at: null,
  revoked_at: null,
};

describe('DevicePairingCard', () => {
  afterEach(() => {
    vi.useRealTimers();
    window.history.replaceState({}, '', '/');
  });

  beforeEach(() => {
    vi.mocked(getCurrentPairedDevice).mockResolvedValue(null);
    vi.mocked(claimDevice).mockResolvedValue(device);
    vi.mocked(listPairedDevices).mockResolvedValue([]);
    vi.mocked(revokeCurrentPairedDevice).mockResolvedValue();
  });

  it('refreshes the linked-device list while the card stays open', async () => {
    vi.mocked(listPairedDevices)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([device]);
    render(<DevicePairingCard isDark />);

    await waitFor(() => expect(listPairedDevices).toHaveBeenCalledTimes(1));
    await act(async () => {
      window.dispatchEvent(new Event('focus'));
      await Promise.resolve();
    });

    expect(await screen.findByText('Kitchen tablet')).toBeInTheDocument();
  });

  it('uses wake events and backs off the host-list fallback', async () => {
    vi.useFakeTimers();
    vi.mocked(listPairedDevices)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue([]);
    render(<DevicePairingCard isDark canManageSystem />);

    expect(listPairedDevices).toHaveBeenCalledTimes(1);
    await vi.runAllTicks();
    await act(async () => { vi.advanceTimersByTime(2_000); });
    expect(listPairedDevices).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(59_999); });
    expect(listPairedDevices).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(listPairedDevices).toHaveBeenCalledTimes(2);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      window.dispatchEvent(new Event('online'));
      await Promise.resolve();
    });
    expect(listPairedDevices).toHaveBeenCalledTimes(3);
  });

  it('removes a prefilled pairing code from the address bar after reading it', async () => {
    window.history.pushState({}, '', '/?pair=ABCD-EFGH');

    render(<DevicePairingCard isDark />);

    expect(screen.getByRole('textbox', { name: 'devicePairingCode' })).toHaveValue('ABCD-EFGH');
    await waitFor(() => expect(window.location.search).toBe(''));
  });

  it('claims, displays, and revokes the current scoped device', async () => {
    const user = userEvent.setup();
    render(<DevicePairingCard isDark />);
    const code = screen.getByRole('textbox', { name: 'devicePairingCode' });
    const name = screen.getByRole('textbox', { name: 'deviceName' });
    await user.clear(name);
    await user.type(name, 'Kitchen tablet');
    await user.type(code, 'ABCD-EFGH');
    await user.click(screen.getByRole('button', { name: 'devicePair' }));

    await waitFor(() => expect(claimDevice).toHaveBeenCalledWith('ABCD-EFGH', 'Kitchen tablet'));
    expect(await screen.findByText('Kitchen tablet')).toBeInTheDocument();
    expect(screen.getByText(/chat, read_private/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'deviceRevoke' }));
    expect(revokeCurrentPairedDevice).not.toHaveBeenCalled();
    const dialog = screen.getByRole('dialog', { name: 'deviceRevokeConfirmTitle' });
    expect(dialog).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'deviceRevoke' }));
    await waitFor(() => expect(revokeCurrentPairedDevice).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: 'devicePair' })).toBeInTheDocument();
  });
});
