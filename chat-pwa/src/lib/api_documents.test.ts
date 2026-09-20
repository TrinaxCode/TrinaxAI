import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  cancelIndexJob,
  extractDocumentText,
  folderLabelFromFiles,
  getIndexJob,
  indexableFilesFrom,
  retryIndexJob,
  startFolderIndex,
} from './api_documents';

class FakeXMLHttpRequest {
  static instances: FakeXMLHttpRequest[] = [];
  method = '';
  url = '';
  timeout = 0;
  responseType = '';
  response: unknown = null;
  status = 0;
  headers = new Map<string, string>();
  sentBody: Document | XMLHttpRequestBodyInit | null = null;
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;

  constructor() { FakeXMLHttpRequest.instances.push(this); }
  open(method: string, url: string) { this.method = method; this.url = url; }
  setRequestHeader(name: string, value: string) { this.headers.set(name, value); }
  send(body: Document | XMLHttpRequestBodyInit | null) { this.sentBody = body; }
  abort() { this.onabort?.(); }
}

function file(name: string, relativePath?: string): File {
  const value = new File(['contents'], name, { type: 'text/plain' });
  if (relativePath) Object.defineProperty(value, 'webkitRelativePath', { value: relativePath });
  return value;
}

function job(extra: Record<string, unknown> = {}) {
  return { id: 'job-1', status: 'indexing', ...extra };
}

beforeEach(() => {
  FakeXMLHttpRequest.instances = [];
  vi.stubGlobal('XMLHttpRequest', FakeXMLHttpRequest);
});

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('document API', () => {
  it('labels folders and filters supported, extensionless, and secret files', () => {
    const readme = file('README', 'project/README');
    const markdown = file('guide.MD', 'project/docs/guide.MD');
    const secret = file('.env.local', 'project/.env.local');
    const key = file('private_key.pem', 'project/private_key.pem');
    const binary = file('image.exe', 'project/image.exe');

    expect(folderLabelFromFiles([readme, markdown])).toBe('project');
    expect(folderLabelFromFiles([])).toBe('import');
    expect(indexableFilesFrom([readme, markdown, secret, key, binary])).toEqual([readme, markdown]);
  });

  it('uploads indexable files, reports progress, and stores the successful import', async () => {
    sessionStorage.setItem('trinaxai-admin-token', 'token');
    const progress = vi.fn();
    const source = file('guide.md', 'project/docs/guide.md');
    const promise = startFolderIndex([source], {
      collectionId: 'docs', watchId: 'watch', embedModel: 'embed', aggressiveQuant: true,
      onUploadProgress: progress,
    });
    const xhr = FakeXMLHttpRequest.instances[0];

    expect(xhr.method).toBe('POST');
    expect(xhr.url).toMatch(/\/system\/index-upload$/);
    expect(xhr.timeout).toBe(300_000);
    expect(xhr.headers.get('X-Admin-Token')).toBe('token');
    expect(Array.from((xhr.sentBody as FormData).entries()).map(([key, value]) => [key, value instanceof File ? value.name : value]))
      .toEqual([
        ['label', 'project'], ['collection_id', 'docs'], ['watch_id', 'watch'],
        ['embed_model', 'embed'], ['aggressive_quant', 'true'], ['files', 'project/docs/guide.md'],
      ]);
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 } as ProgressEvent);
    xhr.status = 202;
    xhr.response = { ok: true, job_id: 'job-1', path: '/tmp/project', saved: 1, skipped: 0, indexed: false };
    xhr.onload?.();

    await expect(promise).resolves.toMatchObject({ job_id: 'job-1' });
    expect(progress.mock.calls.map(([value]) => value)).toEqual([15, 30]);
    expect(JSON.parse(localStorage.getItem('tc-last-index-import') || '{}')).toMatchObject({
      label: 'project', path: '/tmp/project', jobId: 'job-1', saved: 1,
    });
  });

  it('rejects empty inputs, server failures, network failures, timeouts, and aborts', async () => {
    expect(() => startFolderIndex([])).toThrow('No files selected.');
    expect(() => startFolderIndex([file('.env')])).toThrow('No indexable files selected.');

    const server = startFolderIndex([file('a.md')]);
    let xhr = FakeXMLHttpRequest.instances.at(-1)!;
    xhr.status = 415;
    xhr.response = { detail: { code: 'unsupported_format' } };
    xhr.onload?.();
    await expect(server).rejects.toMatchObject({ status: 415, category: 'unsupported_format' });

    const network = startFolderIndex([file('a.md')]);
    xhr = FakeXMLHttpRequest.instances.at(-1)!;
    xhr.onerror?.();
    await expect(network).rejects.toMatchObject({ status: 0 });

    const timeout = startFolderIndex([file('a.md')]);
    xhr = FakeXMLHttpRequest.instances.at(-1)!;
    xhr.ontimeout?.();
    await expect(timeout).rejects.toMatchObject({ status: 0 });

    const controller = new AbortController();
    const aborted = startFolderIndex([file('a.md')], { signal: controller.signal });
    controller.abort();
    await expect(aborted).rejects.toMatchObject({ name: 'AbortError' });

    const preAbortedController = new AbortController();
    preAbortedController.abort();
    await expect(startFolderIndex([file('a.md')], { signal: preAbortedController.signal }))
      .rejects.toMatchObject({ name: 'AbortError' });
  });

  it('gets, cancels, and retries index jobs with validation', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json(job({ progress: 20 })))
      .mockResolvedValueOnce(new Response('missing', { status: 404 }))
      .mockResolvedValueOnce(Response.json({ job: job({ status: 'cancelled' }) }))
      .mockResolvedValueOnce(Response.json({}))
      .mockResolvedValueOnce(new Response('', { status: 409 }))
      .mockResolvedValueOnce(Response.json({ job: job({ status: 'indexing' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const signal = new AbortController().signal;

    await expect(getIndexJob('job/1', signal)).resolves.toMatchObject({ id: 'job-1', progress: 20 });
    await expect(getIndexJob('missing')).rejects.toMatchObject({ status: 404 });
    await expect(cancelIndexJob('job/1')).resolves.toMatchObject({ status: 'cancelled' });
    await expect(cancelIndexJob('job/1')).resolves.toBeNull();
    await expect(cancelIndexJob('job/1')).resolves.toBeNull();
    await expect(retryIndexJob('job/1', signal)).resolves.toMatchObject({ status: 'indexing' });

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/index-jobs\/job%2F1$/);
    expect(fetchMock.mock.calls[2][1].method).toBe('POST');
    expect(fetchMock.mock.calls[5][0]).toMatch(/\/index-jobs\/job%2F1\/retry$/);
  });

  it('extracts a document with progress and handles server, timeout, network, and abort failures', async () => {
    const progress = vi.fn();
    const success = extractDocumentText(file('doc.pdf'), { onUploadProgress: progress });
    let xhr = FakeXMLHttpRequest.instances.at(-1)!;
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 } as ProgressEvent);
    xhr.status = 200;
    xhr.response = { ok: true, name: 'doc.pdf', text: 'hello', chars: 5, truncated: false };
    xhr.onload?.();
    await expect(success).resolves.toMatchObject({ text: 'hello' });
    expect(progress.mock.calls.map(([value]) => value)).toEqual([1, 35, 100]);

    const server = extractDocumentText(file('doc.pdf'));
    xhr = FakeXMLHttpRequest.instances.at(-1)!;
    xhr.status = 422;
    xhr.response = {};
    xhr.onload?.();
    await expect(server).rejects.toMatchObject({ category: 'document_unreadable' });

    const network = extractDocumentText(file('doc.pdf'));
    FakeXMLHttpRequest.instances.at(-1)!.onerror?.();
    await expect(network).rejects.toMatchObject({ status: 0 });

    const timeout = extractDocumentText(file('doc.pdf'));
    FakeXMLHttpRequest.instances.at(-1)!.ontimeout?.();
    await expect(timeout).rejects.toMatchObject({ status: 408 });

    const controller = new AbortController();
    const aborted = extractDocumentText(file('doc.pdf'), { signal: controller.signal });
    controller.abort();
    await expect(aborted).rejects.toMatchObject({ name: 'AbortError' });
  });
});
