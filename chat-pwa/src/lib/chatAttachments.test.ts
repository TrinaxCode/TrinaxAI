import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { deleteChatAttachment, downloadChatAttachment, getChatAttachmentUrl, openChatAttachment, openChatAttachmentInBrowser, shouldOpenWithSystemApplication, storeChatAttachment } from './chatAttachments';

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

  it('falls back to local-only storage when a successful upload has no valid server key', async () => {
    const put = vi.fn((_value: unknown, _key: string) => {
      const request = {
        onsuccess: null as (() => void) | null,
        onerror: null as (() => void) | null,
      };
      queueMicrotask(() => request.onsuccess?.());
      return request;
    });
    const database = {
      objectStoreNames: { contains: () => false },
      createObjectStore: vi.fn((_name: string) => undefined),
      transaction: (_mode: string) => ({ objectStore: () => ({ put }) }),
      close: vi.fn(),
    };
    const openRequest = {
      result: database,
      onupgradeneeded: null as (() => void) | null,
      onsuccess: null as (() => void) | null,
      onerror: null as (() => void) | null,
    };
    vi.stubGlobal('indexedDB', {
      open: vi.fn(() => {
        queueMicrotask(() => {
          openRequest.onupgradeneeded?.();
          openRequest.onsuccess?.();
        });
        return openRequest;
      }),
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) }));

    try {
      const attachment = await storeChatAttachment(new File(['content'], 'manual.pdf', { type: 'application/pdf' }), 'document');

      expect(attachment.localOnly).toBe(true);
      expect(attachment.storageKey).toMatch(/^attachment-/);
      expect(put).toHaveBeenCalledOnce();
    } finally {
      vi.unstubAllGlobals();
    }
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

  it('opens Office attachments through the host default application endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    expect(shouldOpenWithSystemApplication({ name: 'slides.pptx', mimeType: 'application/octet-stream' })).toBe(true);
    expect(await openChatAttachment(`server:${'c'.repeat(32)}`)).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(`/api/rag/attachments/${'c'.repeat(32)}/open`, expect.objectContaining({ method: 'POST' }));
  });

  it('renews the authenticated server download and preserves the client filename', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(['content'], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:download'), revokeObjectURL: vi.fn() });

    expect(await downloadChatAttachment({
      storageKey: `server:${'d'.repeat(32)}`,
      name: 'plan.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })).toBe(true);

    expect(fetchMock).toHaveBeenCalledWith(`/api/rag/attachments/${'d'.repeat(32)}`, expect.objectContaining({ headers: expect.any(Headers) }));
    expect(click).toHaveBeenCalledOnce();
    expect(document.querySelector('a[download="plan.docx"]')).toBeNull();
    click.mockRestore();
  });

  it('opens and downloads an existing preview URL without refetching it', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue({} as Window);
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    expect(await openChatAttachmentInBrowser({ name: 'photo.png', mimeType: 'image/png', storageKey: undefined }, 'data:image/png;base64,abc')).toBe(true);
    expect(await downloadChatAttachment({ name: 'photo.png', mimeType: 'image/png', storageKey: undefined }, 'data:image/png;base64,abc')).toBe(true);
    expect(open).toHaveBeenCalledWith('data:image/png;base64,abc', '_blank', 'noopener,noreferrer');
    expect(click).toHaveBeenCalledOnce();
    expect(fetchMock).not.toHaveBeenCalled();
    open.mockRestore();
    click.mockRestore();
  });

  it('does not open active HTML or SVG content in a top-level tab', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue({} as Window);

    expect(await openChatAttachmentInBrowser({ name: 'payload.html', mimeType: 'text/html' }, 'blob:payload')).toBe(false);
    expect(await openChatAttachmentInBrowser({ name: 'icon.svg', mimeType: 'image/svg+xml' }, 'blob:icon')).toBe(false);
    expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });
});
