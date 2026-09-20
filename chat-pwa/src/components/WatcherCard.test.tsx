import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  deleteIndexedImport: vi.fn(),
  getWatchStatus: vi.fn(),
  startFolderIndex: vi.fn(),
  startWatch: vi.fn(),
  stopWatch: vi.fn(),
  userFacingError: vi.fn(() => 'friendly error'),
}));
const toast = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock('../lib/api', () => api);
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('./Toast', () => ({ useToast: () => toast }));

import WatcherCard from './WatcherCard';

const status = (running = false) => ({
  running, watching: ['/tmp'], events_seen: running ? 2 : 0, started_at: 1,
  job: { status: running ? 'running' : 'idle', pending_events: running ? 1 : 0, active_root: '/tmp', last_started_at: 1, last_finished_at: null, last_duration_seconds: null, last_exit_code: null, last_error: running ? 'last error' : null, last_stdout: '', last_stderr: '', runs_completed: 1, runs_failed: 0, runs_timed_out: 0, runs_cancelled: 0 },
});

describe('watcher card lifecycle', () => {
  beforeEach(() => {
    api.deleteIndexedImport.mockReset().mockResolvedValue({ deleted: 1 });
    api.getWatchStatus.mockReset().mockResolvedValue(status(true));
    api.startFolderIndex.mockReset().mockResolvedValue({ path: '/tmp/project' });
    api.startWatch.mockReset().mockResolvedValue({ status: 'started' });
    api.stopWatch.mockReset().mockResolvedValue({ status: 'stopped' });
    toast.toast.mockClear();
    delete (window as any).showDirectoryPicker;
  });

  it('loads server status, adds files, starts/stops a host watcher, and removes a folder', async () => {
    const user = userEvent.setup();
    render(<WatcherCard collections={[{ id: 'docs', name: 'Docs' }]} />);
    await waitFor(() => expect(api.getWatchStatus).toHaveBeenCalled());
    expect(screen.getByText(/watcherIndexStatus/)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('watcherLastError');

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['text'], 'guide.md', { type: 'text/markdown' });
    Object.defineProperty(file, 'webkitRelativePath', { value: 'project/guide.md' });
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    fireEvent.change(input);
    expect(await screen.findByText('project')).toBeInTheDocument();
    expect(api.startFolderIndex).toHaveBeenCalledWith([file], expect.objectContaining({ collectionId: 'docs' }));

    await user.click(screen.getByRole('button', { name: 'stop' }));
    expect(api.stopWatch).toHaveBeenCalled();
    // A populated folder without a host path is a supported local watcher.
    await user.click(screen.getByRole('button', { name: 'start' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'stop' })).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: 'deleteFolder project' }));
    await user.click(screen.getByRole('button', { name: 'delete' }));
    await waitFor(() => expect(api.deleteIndexedImport).toHaveBeenCalledWith('/tmp/project', 'docs'));
  });

  it('uses a host path watcher and reports start failures', async () => {
    api.getWatchStatus.mockResolvedValueOnce(status(false)).mockResolvedValue(status(true));
    api.startWatch.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ status: 'started' });
    const user = userEvent.setup();
    render(<WatcherCard collections={[{ id: 'default', name: 'General' }]} />);
    const path = screen.getByRole('textbox', { name: 'watcherHostPath' });
    await user.type(path, '/tmp/project');
    await user.click(screen.getByRole('button', { name: 'start' }));
    await waitFor(() => expect(toast.toast).toHaveBeenCalledWith('friendly error', 'error'));
    await user.click(screen.getByRole('button', { name: 'start' }));
    await waitFor(() => expect(api.startWatch).toHaveBeenCalledWith({ paths: ['/tmp/project'], collection: 'default' }));
    expect(screen.getByRole('button', { name: 'stop' })).toBeInTheDocument();
  });

  it('walks a directory picker and treats cancellation as harmless', async () => {
    const file = new File(['text'], 'nested.md', { type: 'text/markdown' });
    const handle = { name: 'folder', entries: async function* () { yield ['nested.md', { getFile: async () => file }]; } } as any;
    (window as any).showDirectoryPicker = vi.fn().mockResolvedValue(handle);
    const view = render(<WatcherCard collections={[{ id: 'default', name: 'General' }]} />);
    await userEvent.click(screen.getByRole('button', { name: 'watcherAddFolder' }));
    expect(await screen.findByText('folder')).toBeInTheDocument();
    view.unmount();
    delete (window as any).showDirectoryPicker;
    api.getWatchStatus.mockResolvedValue(status(false));
    render(<WatcherCard collections={[]} />);
    expect(screen.getByRole('button', { name: 'start' })).toBeDisabled();
  });
});
