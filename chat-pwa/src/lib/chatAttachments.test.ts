import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { deleteChatAttachment, getChatAttachmentUrl, storeChatAttachment } from './chatAttachments';

describe('server-backed chat attachments', () => {
  beforeEach(() => sessionStorage.setItem('trinaxai-admin-token', 'test-secret'));
  afterEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it('stores a server key that can be synchronized between devices', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'a'.repeat(32),
          storage_key: `server:${'a'.repeat(32)}`,
          name: 'manual.pdf',
          size: 7,
          mime_type: 'application/pdf',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        blob: async () => new Blob(['content'], { type: 'application/pdf' }),
      });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:server-attachment'),
    });

    const attachment = await storeChatAttachment(
      new File(['content'], 'manual.pdf', { type: 'application/pdf' }),
      'document',
    );

    expect(attachment.storageKey).toBe(`server:${'a'.repeat(32)}`);
    expect(await getChatAttachmentUrl(attachment.storageKey, attachment.mimeType)).toBe('blob:server-attachment');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const uploadHeaders = fetchMock.mock.calls[0][1]?.headers as Headers;
    const downloadHeaders = fetchMock.mock.calls[1][1]?.headers as Headers;
    expect(uploadHeaders.get('X-Admin-Token')).toBe('test-secret');
    expect(uploadHeaders.has('Content-Type')).toBe(false);
    expect(downloadHeaders.get('X-Admin-Token')).toBe('test-secret');
  });

  it('deletes server attachments with the session credential', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchMock);

    await deleteChatAttachment({
      name: 'manual.pdf',
      size: 7,
      storageKey: `server:${'b'.repeat(32)}`,
      kind: 'document',
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/rag/attachments/${'b'.repeat(32)}`);
    expect(options.method).toBe('DELETE');
    expect((options.headers as Headers).get('X-Admin-Token')).toBe('test-secret');
  });
});
