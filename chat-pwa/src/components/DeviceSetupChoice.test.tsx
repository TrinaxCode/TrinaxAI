import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import DeviceSetupChoice from './DeviceSetupChoice';

vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('./DevicePairingCard', () => ({ default: () => <div data-testid="pairing-card" /> }));

describe('DeviceSetupChoice', () => {
  it('opens recovery directly when the server already has an installation', () => {
    render(<DeviceSetupChoice preferExisting onNewDevice={vi.fn()} />);
    expect(screen.getByRole('heading', { name: 'deviceSetupRestoreTitle' })).toBeInTheDocument();
    expect(screen.getByTestId('pairing-card')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /deviceSetupNew/ })).not.toBeInTheDocument();
  });

  it('uses the shared back icon and restores focus when returning to the choice', async () => {
    const user = userEvent.setup();
    render(<DeviceSetupChoice onNewDevice={vi.fn()} />);

    const existing = screen.getByRole('button', { name: /deviceSetupExisting/ });
    await user.click(existing);
    const back = screen.getByRole('button', { name: 'back' });

    expect(back).toHaveClass('min-h-11', 'min-w-11');
    expect(back.querySelector('svg')).toBeInTheDocument();
    expect(back).toHaveFocus();

    await user.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: /deviceSetupExisting/ })).toHaveFocus();
  });

  it('shows progress and then an error when new device setup fails', async () => {
    const user = userEvent.setup();
    let reject!: (reason: Error) => void;
    const onNewDevice = vi.fn(() => new Promise<void>((_resolve, fail) => { reject = fail; }));
    render(<DeviceSetupChoice onNewDevice={onNewDevice} />);

    await user.click(screen.getByRole('button', { name: /deviceSetupNew/ }));
    expect(screen.getByRole('button', { name: /loading/ })).toBeDisabled();
    reject(new Error('unavailable'));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('deviceSetupNewError'));
    expect(screen.getByRole('button', { name: /deviceSetupNew/ })).toBeEnabled();
  });
});
