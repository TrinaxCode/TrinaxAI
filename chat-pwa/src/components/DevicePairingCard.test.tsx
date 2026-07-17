import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DevicePairingCard from './DevicePairingCard';
import { claimDevice, getCurrentPairedDevice, revokeCurrentPairedDevice } from '../lib/devicePairing';

vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
vi.mock('../lib/devicePairing', () => ({
  claimDevice: vi.fn(),
  getCurrentPairedDevice: vi.fn(),
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
  beforeEach(() => {
    vi.mocked(getCurrentPairedDevice).mockResolvedValue(null);
    vi.mocked(claimDevice).mockResolvedValue(device);
    vi.mocked(revokeCurrentPairedDevice).mockResolvedValue();
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
