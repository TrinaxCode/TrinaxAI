import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MemoryPanel from './MemoryPanel';
import {
  addMemory,
  getMemorySummary,
  listMemories,
  updateMemory,
  type MemoryEntry,
  type MemorySummary,
} from '../lib/api';

const toast = vi.fn();

vi.mock('../i18n/I18nContext', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));
vi.mock('./Toast', () => ({
  useToast: () => ({ toast }),
}));
vi.mock('../lib/api', () => ({
  listMemories: vi.fn(),
  getMemorySummary: vi.fn(),
  addMemory: vi.fn(),
  deleteMemory: vi.fn(),
  refreshMemorySummary: vi.fn(),
  updateMemory: vi.fn(),
  userFacingError: (error: unknown) => error instanceof Error ? error.message : 'unknown error',
}));

describe('MemoryPanel', () => {
  beforeEach(() => {
    vi.mocked(listMemories).mockResolvedValue([]);
    vi.mocked(getMemorySummary).mockResolvedValue({ summary: '', count: 0, updated_at: 0 });
    vi.mocked(addMemory).mockResolvedValue({
      id: 'memory-1',
      text: 'Prefiero Python',
      tags: ['python'],
      created_at: 1,
      kind: 'note',
      provenance: 'manual',
    });
    vi.mocked(updateMemory).mockResolvedValue({
      id: 'memory-1',
      text: 'Prefiero Python',
      tags: ['python'],
      created_at: 1,
      kind: 'preference',
      provenance: 'manual',
    });
    toast.mockClear();
    localStorage.clear();
  });

  it('loads memory state and creates a tagged persistent memory', async () => {
    const user = userEvent.setup();
    render(<MemoryPanel canManageSystem />);

    await waitFor(() => expect(listMemories).toHaveBeenCalled());
    await user.type(screen.getByPlaceholderText('memoryTextPlaceholder'), 'Prefiero Python');
    await user.type(screen.getByPlaceholderText('memoryTagsPlaceholder'), 'python, preferencias');
    await user.click(screen.getByRole('button', { name: /add/i }));

    await waitFor(() => {
      expect(addMemory).toHaveBeenCalledWith(
        'Prefiero Python',
        ['python', 'preferencias'],
        { kind: 'note', expiresAt: undefined },
      );
    });
    expect(toast).toHaveBeenCalledWith('memoryAdded', 'success');
  });

  it('surfaces backend failures instead of pretending memory is empty', async () => {
    vi.mocked(listMemories).mockRejectedValue(new Error('memory backend unavailable'));

    render(<MemoryPanel />);

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith('memory backend unavailable', 'error');
    });
  });

  it('does not let an older refresh overwrite a newer memory list', async () => {
    vi.mocked(listMemories).mockReset();
    vi.mocked(getMemorySummary).mockReset();
    let resolveInitialList!: (value: MemoryEntry[]) => void;
    let resolveInitialSummary!: (value: MemorySummary) => void;
    const freshMemory: MemoryEntry = {
      id: 'memory-fresh',
      text: 'fresh memory',
      tags: [],
      created_at: 2,
      kind: 'note',
      provenance: 'manual',
    };
    vi.mocked(listMemories)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveInitialList = resolve; }))
      .mockResolvedValueOnce([freshMemory]);
    vi.mocked(getMemorySummary)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveInitialSummary = resolve; }))
      .mockResolvedValueOnce({ summary: 'fresh summary', count: 1, updated_at: 2 });

    const user = userEvent.setup();
    render(<MemoryPanel canManageSystem />);
    await waitFor(() => expect(listMemories).toHaveBeenCalledOnce());
    await user.type(screen.getByPlaceholderText('memoryTextPlaceholder'), 'new memory');
    await user.click(screen.getByRole('button', { name: /add/i }));
    await waitFor(() => expect(listMemories).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText('fresh memory')).toBeInTheDocument());

    await act(async () => {
      resolveInitialList([]);
      resolveInitialSummary({ summary: '', count: 0, updated_at: 0 });
    });
    expect(screen.getByText('fresh memory')).toBeInTheDocument();
  });
});
