import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import App from './App';

const session = {
  id: 'test-session',
  title: 'Test',
  engine: 'ollama' as const,
  messages: [],
  createdAt: 1,
  updatedAt: 1,
};

vi.mock('./theme/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
vi.mock('./i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('./components/Intro', () => ({ default: () => <div data-testid="intro" /> }));
vi.mock('./components/DeviceSetupChoice', () => ({ default: () => <div data-testid="device-setup" /> }));
vi.mock('./components/Background', () => ({
  default: ({ active }: { active?: boolean }) => (
    <div data-testid="background" data-active={String(active ?? true)} />
  ),
}));
vi.mock('./lib/sharedState', () => ({
  onSharedStateUpdated: () => () => undefined,
  startSharedStateSync: () => undefined,
  syncSharedStateOnce: async () => undefined,
}));
vi.mock('./lib/devicePairing', () => ({ startDeviceRevocationMonitor: () => undefined }));
vi.mock('./lib/deviceWipe', () => ({ wipeRevokedDeviceData: async () => undefined }));
vi.mock('./hooks/useChatHistory', () => ({
  useChatHistory: () => ({
    sessions: [session],
    activeSession: session,
    activeId: session.id,
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    selectSession: vi.fn(),
    updateSession: vi.fn(),
    setEngine: vi.fn(),
    folders: [],
    createFolder: vi.fn(),
    moveSessionToFolder: vi.fn(),
    deleteFolder: vi.fn(),
  }),
}));

describe('App background handoff', () => {
  it('keeps the waves active while the welcome screen is still visible', () => {
    render(<App />);
    expect(screen.getByTestId('intro')).toBeInTheDocument();
    expect(screen.getByTestId('background')).toHaveAttribute('data-active', 'true');
  });

  it('returns to device setup when the current device loses access', async () => {
    render(<App />);
    window.dispatchEvent(new CustomEvent('trinaxai-device-access-revoked'));

    expect(await screen.findByTestId('device-setup')).toBeInTheDocument();
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument();
  });
});
