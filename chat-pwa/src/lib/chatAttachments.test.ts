import { afterEach, describe, expect, it, vi } from 'vitest';
import { getChatAttachmentUrl, storeChatAttachment } from './chatAttachments';

describe('server-backed chat attachments', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('stores a server key that can be synchronized between devices', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'a'.repeat(32),
        storage_key: `server:${'a'.repeat(32)}`,
        name: 'manual.pdf',
        size: 7,
        mime_type: 'application/pdf',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const attachment = await storeChatAttachment(
      new File(['content'], 'manual.pdf', { type: 'application/pdf' }),
      'document',
    );

    expect(attachment.storageKey).toBe(`server:${'a'.repeat(32)}`);
    expect(await getChatAttachmentUrl(attachment.storageKey)).toBe(
      `/api/rag/attachments/${'a'.repeat(32)}`,
    );
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
