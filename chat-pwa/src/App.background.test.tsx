import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
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
vi.mock('./components/OnboardingWizard', () => ({ default: () => <div data-testid="onboarding-wizard" /> }));
vi.mock('./components/DeviceSetupChoice', () => ({ default: () => <div data-testid="device-setup" /> }));
vi.mock('./components/ChatInterface', () => ({ default: () => <div data-testid="chat-interface" /> }));
vi.mock('./components/ChatSidebar', () => ({ default: () => <div data-testid="chat-sidebar" /> }));
vi.mock('./components/NetworkNotice', () => ({ default: () => <div data-testid="network-notice" /> }));
vi.mock('./components/PermissionNotice', () => ({ default: () => <div data-testid="permission-notice" /> }));
vi.mock('./components/Docs', () => ({ default: () => <div data-testid="docs" /> }));
vi.mock('./components/KnowledgeBrowser', () => ({ default: () => <div data-testid="knowledge-browser" /> }));
vi.mock('./components/AgentInterface', () => ({ default: () => <div data-testid="agent-interface" /> }));
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

describe('App startup handoff', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ existingInstallation: false }) }));
  });

  it('renders the background without a welcome splash', () => {
    render(<App />);
    expect(screen.getByTestId('background')).toHaveAttribute('data-active', 'true');
    expect(screen.queryByTestId('intro')).not.toBeInTheDocument();
  });

  it('opens the onboarding wizard directly for a fresh installation', async () => {
    render(<App />);

    expect(await screen.findByTestId('onboarding-wizard')).toBeInTheDocument();
    expect(screen.queryByTestId('device-setup')).not.toBeInTheDocument();
  });

  it('opens device recovery when the host already has an installation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ existingInstallation: true }) }));
    render(<App />);

    expect(await screen.findByTestId('device-setup')).toBeInTheDocument();
    expect(screen.queryByTestId('onboarding-wizard')).not.toBeInTheDocument();
  });

  it('does not open first-run screens after onboarding is complete', async () => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    render(<App />);

    await waitFor(() => expect(screen.queryByTestId('onboarding-wizard')).not.toBeInTheDocument());
    expect(screen.queryByTestId('device-setup')).not.toBeInTheDocument();
  });

  it('returns to device setup when the current device loses access', async () => {
    render(<App />);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/network', { cache: 'no-store' }));
    window.dispatchEvent(new CustomEvent('trinaxai-device-access-revoked'));

    await waitFor(() => expect(screen.getByTestId('device-setup')).toBeInTheDocument());
  });
});
