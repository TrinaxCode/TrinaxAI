import { render, screen } from '@testing-library/react';
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
});
