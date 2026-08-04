import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KnowledgeBrowser from './KnowledgeBrowser';

const apiMocks = vi.hoisted(() => ({
  getCollections: vi.fn(),
  getCollectionSources: vi.fn(),
  getFileChunks: vi.fn(),
  deleteCollectionSources: vi.fn(),
  deleteSource: vi.fn(),
}));

vi.mock('../lib/api', () => apiMocks);
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('./Toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const source = (file: string, sourceId = 'root') => ({
  file,
  source_id: sourceId,
  chunks: 1,
  size: 20,
  mtime: 1,
  preview: 'preview',
});

const chunk = (id: string, text: string) => ({
  id,
  text,
  metadata: {},
  score: null,
});

describe('KnowledgeBrowser request races', () => {
  beforeEach(() => {
    apiMocks.getCollections.mockResolvedValue([
      { id: 'default', name: 'General', created_at: 1, updated_at: 1 },
      { id: 'docs', name: 'Docs', created_at: 1, updated_at: 1 },
    ]);
    apiMocks.getCollectionSources.mockReset();
    apiMocks.getFileChunks.mockReset();
  });

  it('ignores a stale collection response after switching collections', async () => {
    const general = deferred<{ collection: string; sources: ReturnType<typeof source>[] }>();
    apiMocks.getCollectionSources
      .mockReturnValueOnce(general.promise)
      .mockResolvedValueOnce({ collection: 'docs', sources: [source('docs/manual.md')] });

    render(<KnowledgeBrowser onBack={vi.fn()} />);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Docs' }).length).toBeGreaterThan(0));
    const docsButtons = screen.getAllByRole('button', { name: 'Docs' });
    await userEvent.click(docsButtons[0]);
    general.resolve({ collection: 'default', sources: [source('stale.md')] });

    await waitFor(() => expect(screen.getByText('docs/manual.md')).toBeInTheDocument());
    expect(screen.queryByText('stale.md')).not.toBeInTheDocument();
  });

  it('keeps the newest file chunks when an older request resolves later', async () => {
    apiMocks.getCollectionSources.mockResolvedValue({
      collection: 'docs',
      sources: [source('a.md', 'alpha'), source('b.md', 'beta')],
    });
    const first = deferred<{ collection: string; file: string; total: number; chunks: ReturnType<typeof chunk>[] }>();
    apiMocks.getFileChunks
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ collection: 'docs', file: 'b.md', total: 1, chunks: [chunk('b', 'B')] });

    render(<KnowledgeBrowser onBack={vi.fn()} initialCollection="docs" initialFile="a.md" />);
    await waitFor(() => expect(screen.getAllByText('b.md').length).toBeGreaterThan(0));
    const bButton = screen.getAllByText('b.md')[0].closest('button');
    expect(bButton).not.toBeNull();
    await userEvent.click(bButton!);
    first.resolve({ collection: 'docs', file: 'a.md', total: 0, chunks: [] });

    await waitFor(() => expect(screen.getByText('B')).toBeInTheDocument());
    expect(screen.queryByText('A')).not.toBeInTheDocument();
    expect(screen.getByText('1 chunksTotal')).toBeInTheDocument();
  });
});
