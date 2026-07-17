import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MemoryPanel from './MemoryPanel';
import {
  addMemory,
  getMemorySummary,
  listMemories,
  updateMemory,
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
    render(<MemoryPanel />);

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
});
