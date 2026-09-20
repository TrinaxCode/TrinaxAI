import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  extractDocumentText: vi.fn(),
  getIndexJob: vi.fn(),
  startFolderIndex: vi.fn(),
  prepareImageForVision: vi.fn(),
  userFacingError: vi.fn(() => 'friendly error'),
}));
const audio = vi.hoisted(() => ({ play: vi.fn() }));
const attachments = vi.hoisted(() => ({
  canOpenChatAttachmentInBrowser: vi.fn(() => true),
  downloadChatAttachment: vi.fn(async () => true),
  getChatAttachmentUrl: vi.fn(async () => 'blob:preview'),
  openChatAttachment: vi.fn(async () => false),
  openChatAttachmentInBrowser: vi.fn(() => true),
  shouldOpenWithSystemApplication: vi.fn(() => false),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  extractDocumentText: api.extractDocumentText,
  getIndexJob: api.getIndexJob,
  startFolderIndex: api.startFolderIndex,
  prepareImageForVision: api.prepareImageForVision,
  userFacingError: api.userFacingError,
}));
vi.mock('../services/audioManager', () => ({ audioManager: audio }));
vi.mock('../lib/chatAttachments', () => attachments);

import { useChatAttachments } from './useChatAttachments';
import { useChatDocuments } from './useChatDocuments';

const t = (key: string) => key.replace(/[A-Z]/g, (letter) => ` ${letter.toLowerCase()}`);
const textFile = (name: string, text = 'document text') => new File([text], name, { type: 'text/plain' });
const imageFile = (name: string) => new File(['image'], name, { type: 'image/png' });

describe('document attachment hook', () => {
  beforeEach(() => {
    api.extractDocumentText.mockReset();
    api.getIndexJob.mockReset();
    api.startFolderIndex.mockReset();
    api.userFacingError.mockClear();
    audio.play.mockClear();
    attachments.getChatAttachmentUrl.mockClear();
    vi.useRealTimers();
  });

  it('filters unsupported files, extracts documents, records failures, and clears them', async () => {
    api.extractDocumentText
      .mockResolvedValueOnce({ text: 'A'.repeat(100), truncated: false })
      .mockRejectedValueOnce(new Error('bad document'));
    const { result } = renderHook(() => useChatDocuments({
      collections: [{ id: 'docs', name: 'Docs', created_at: 1, updated_at: 1 }],
      initialCollectionId: 'missing',
      t,
    }));
    expect(result.current.docIndexCollectionId).toBe('docs');
    const files = [textFile('good.md', 'A'.repeat(100)), textFile('bad.md'), imageFile('ignored.png')];
    await act(async () => { await result.current.processDocumentFiles(files); });
    expect(result.current.docIndexCollectionId).toBe('docs');
    expect(result.current.attachedDocs).toHaveLength(1);
    expect(result.current.attachedDocs[0]).toMatchObject({ name: 'good.md', truncated: false });
    expect(result.current.docUploadStatus).toContain('chat docs attached');
    expect(api.extractDocumentText).toHaveBeenCalledTimes(2);
    expect(audio.play).toHaveBeenCalledWith('file-processing');
    expect(audio.play).toHaveBeenCalledWith('file-ready');
    act(() => result.current.clearAttachedDocs());
    expect(result.current.attachedDocs).toEqual([]);
    await act(async () => { await result.current.processDocumentFiles([imageFile('not-a-doc.png')]); });
    expect(result.current.docUploadStatus).toContain('chat upload no files');
  });

  it('queues an index without a job and polls completed, failed, and cancelled jobs', async () => {
    api.extractDocumentText.mockResolvedValue({ text: 'content', truncated: false });
    const { result } = renderHook(() => useChatDocuments({
      collections: [{ id: 'default', name: 'General', created_at: 1, updated_at: 1 }],
      initialCollectionId: 'default', t,
    }));
    await act(async () => { await result.current.processDocumentFiles([textFile('guide.md')]); });
    api.startFolderIndex.mockResolvedValueOnce({ saved: 1 }).mockResolvedValue({ job_id: 'job-1', saved: 1 });
    await act(async () => { await result.current.indexAttachedDocs(); });
    expect(result.current.docUploadStatus).toContain('chat upload queued');

    api.getIndexJob.mockResolvedValueOnce({ status: 'indexing', progress: 20 })
      .mockResolvedValueOnce({ status: 'completed', saved: 1 });
    vi.useFakeTimers();
    const complete = result.current.indexAttachedDocs();
    await act(async () => { await vi.advanceTimersByTimeAsync(2200); });
    await act(async () => { await complete; });
    expect(result.current.docUploadStatus).toContain('chat upload done');
    vi.useRealTimers();

    api.getIndexJob.mockResolvedValue({ status: 'failed', error: 'broken' });
    vi.useFakeTimers();
    const failed = result.current.indexAttachedDocs();
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
    await act(async () => { await failed; });
    expect(result.current.docUploadStatus).toContain('friendly error');
  });

  it('rebuilds stored document context and safely skips missing attachments', async () => {
    const blob = new Blob(['stored text'], { type: 'text/plain' });
    api.extractDocumentText.mockResolvedValue({ text: 'stored text', truncated: false });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(blob)));
    const { result } = renderHook(() => useChatDocuments({ collections: [], initialCollectionId: 'default', t }));
    await expect(result.current.rebuildStoredDocumentContext({ role: 'user', content: 'prompt', documentAttachments: [
      { kind: 'document', name: 'stored.md', storageKey: 'key', mimeType: 'text/markdown' },
      { kind: 'image', name: 'image.png', storageKey: 'image' },
    ] })).resolves.toContain('stored.md');
    expect(attachments.getChatAttachmentUrl).toHaveBeenCalledWith('key', 'text/markdown');
    await expect(result.current.rebuildStoredDocumentContext({ role: 'user', content: 'plain' })).resolves.toBe('');
  });
});

describe('chat attachment hook', () => {
  beforeEach(() => {
    api.prepareImageForVision.mockReset();
    api.userFacingError.mockClear();
    attachments.canOpenChatAttachmentInBrowser.mockReturnValue(true);
    attachments.shouldOpenWithSystemApplication.mockReturnValue(false);
  });

  it('processes images, limits selections, and routes dropped documents', async () => {
    api.prepareImageForVision.mockResolvedValueOnce('data:image/png;base64,one').mockRejectedValueOnce(new Error('bad image'));
    const processDocumentFiles = vi.fn();
    const { result } = renderHook(() => useChatAttachments({ callMode: false, processDocumentFiles, t }));
    const files = [imageFile('one.png'), imageFile('bad.png'), textFile('guide.md')];
    const dataTransfer = { files, types: ['Files'], dropEffect: '' } as unknown as DataTransfer;
    await act(async () => { result.current.handleDrop({ dataTransfer, preventDefault: vi.fn() } as any); });
    await waitFor(() => expect(result.current.attachedImages).toHaveLength(1));
    expect(processDocumentFiles).toHaveBeenCalledWith([files[2]]);
    expect(result.current.imageError).toContain('chat images omitted');
    const paste = { clipboardData: dataTransfer, preventDefault: vi.fn() } as any;
    act(() => result.current.handlePaste(paste));
    expect(paste.preventDefault).toHaveBeenCalled();
  });

  it('handles drag state, preview text, open, download, and call-mode guards', async () => {
    const { result, rerender } = renderHook(({ callMode }) => useChatAttachments({ callMode, processDocumentFiles: vi.fn(), t }), { initialProps: { callMode: false } });
    const preventDefault = vi.fn();
    const event = { dataTransfer: { types: ['Files'], dropEffect: '' }, preventDefault } as any;
    act(() => result.current.handleDragEnter(event));
    expect(result.current.dragActive).toBe(true);
    act(() => result.current.handleDragOver(event));
    expect(event.dataTransfer.dropEffect).toBe('copy');
    act(() => result.current.handleDragLeave({ relatedTarget: null } as any));
    expect(result.current.dragActive).toBe(false);
    await act(async () => { await result.current.openStoredAttachment({ kind: 'document', name: 'notes.md', storageKey: 'key', mimeType: 'text/markdown' }); });
    await waitFor(() => expect(result.current.textPreview).toBe(null));
    await expect(result.current.openPreviewAttachment()).resolves.toBe(true);
    await expect(result.current.downloadPreviewAttachment()).resolves.toBe(true);
    rerender({ callMode: true });
    act(() => result.current.handleDragEnter(event));
    expect(result.current.dragActive).toBe(false);
  });
});
