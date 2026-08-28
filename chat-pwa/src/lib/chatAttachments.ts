import type { ChatDocumentAttachment } from './api';
import { APP_CONFIG } from './config';
import { isLocalAuthority, systemRequestHeaders } from './authHeaders';

const RAG_BASE = APP_CONFIG.ragBase;

const DB_NAME = 'trinaxai-chat-files';
const STORE_NAME = 'files';
const SERVER_ATTACHMENT_ID = /^[0-9a-f]{32}$/;

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function storeChatAttachment(file: File, kind: ChatDocumentAttachment['kind']): Promise<ChatDocumentAttachment> {
  // The server copy is what makes a synced conversation's files available on
  // another browser/device. IndexedDB below remains a compatibility fallback
  // for offline sessions and older backends.
  try {
    const form = new FormData();
    form.append('file', file, file.name);
    const response = await fetch(`${RAG_BASE}/attachments`, {
      method: 'POST',
      body: form,
      headers: systemRequestHeaders(),
    });
    if (!response.ok) throw new Error(`Attachment upload failed: ${response.status}`);
    const stored = await response.json() as Record<string, unknown>;
    const id = typeof stored.id === 'string' ? stored.id : '';
    const storageKey = typeof stored.storage_key === 'string' ? stored.storage_key : '';
    if (!SERVER_ATTACHMENT_ID.test(id) || storageKey !== `server:${id}`) {
      throw new Error('Invalid attachment upload response');
    }
    return {
      id,
      storageKey,
      name: typeof stored.name === 'string' && stored.name ? stored.name : file.name,
      size: typeof stored.size === 'number' && Number.isFinite(stored.size) ? stored.size : file.size,
      mimeType: typeof stored.mime_type === 'string' && stored.mime_type
        ? stored.mime_type
        : file.type || 'application/octet-stream',
      kind,
    };
  } catch {
    // A local copy still lets the sender open the file if the backend is an
    // older version or temporarily unavailable.
  }
  const id = `attachment-${crypto.randomUUID()}`;
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const request = db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).put(file, id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
  db.close();
  return { id, storageKey: id, name: file.name, size: file.size, mimeType: file.type || 'application/octet-stream', kind, localOnly: true };
}

export async function deleteChatAttachment(attachment: ChatDocumentAttachment): Promise<void> {
  const storageKey = attachment.storageKey;
  if (!storageKey) return;
  if (storageKey.startsWith('server:')) {
    const attachmentId = storageKey.slice('server:'.length);
    if (/^[0-9a-f]{32}$/.test(attachmentId)) {
      await fetch(`${RAG_BASE}/attachments/${attachmentId}`, {
        method: 'DELETE',
        headers: systemRequestHeaders(),
      }).then((response) => {
        if (!response.ok && response.status !== 404) throw new Error(`Attachment delete failed: ${response.status}`);
      });
    }
    return;
  }
  if (typeof indexedDB === 'undefined') return;
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const request = db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).delete(storageKey);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
  db.close();
}

export async function deleteChatAttachments(messages: Array<{ documentAttachments?: ChatDocumentAttachment[] }>): Promise<void> {
  const attachments = [...new Map(
    messages.flatMap((message) => message.documentAttachments ?? [])
      .filter((attachment) => attachment.storageKey)
      .map((attachment) => [attachment.storageKey, attachment]),
  ).values()];
  await Promise.allSettled(attachments.map(deleteChatAttachment));
}

async function getChatAttachmentBlob(storageKey?: string, mimeType?: string, fallbackUrl?: string): Promise<Blob | null> {
  if (!storageKey) {
    return fallbackUrl ? fetch(fallbackUrl).then((response) => response.ok ? response.blob() : null).catch(() => null) : null;
  }
  if (storageKey.startsWith('server:')) {
    const attachmentId = storageKey.slice('server:'.length);
    if (SERVER_ATTACHMENT_ID.test(attachmentId)) {
      try {
        const response = await fetch(`${RAG_BASE}/attachments/${attachmentId}`, {
          headers: systemRequestHeaders(),
        });
        if (!response.ok) return null;
        const blob = await response.blob();
        return mimeType && blob.type !== mimeType ? new Blob([blob], { type: mimeType }) : blob;
      } catch {
        return null;
      }
    }
    return fallbackUrl ? fetch(fallbackUrl).then((response) => response.ok ? response.blob() : null).catch(() => null) : null;
  }
  if (typeof indexedDB === 'undefined') return null;
  try {
    const db = await openDb();
    const blob = await new Promise<Blob | null>((resolve, reject) => {
      const request = db.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).get(storageKey);
      request.onsuccess = () => resolve(request.result instanceof Blob ? request.result : null);
      request.onerror = () => reject(request.error);
    });
    db.close();
    if (!blob) return null;
    return mimeType && blob.type !== mimeType ? new Blob([blob], { type: mimeType }) : blob;
  } catch {
    return null;
  }
}

export async function getChatAttachmentUrl(storageKey?: string, mimeType?: string): Promise<string | null> {
  const blob = await getChatAttachmentBlob(storageKey, mimeType);
  return blob ? URL.createObjectURL(blob) : null;
}

type AttachmentReference = Pick<ChatDocumentAttachment, 'name' | 'mimeType' | 'storageKey'>;

const ACTIVE_CONTENT_MIME_TYPES = new Set([
  'application/xhtml+xml',
  'application/javascript',
  'text/html',
  'text/javascript',
  'image/svg+xml',
]);
const ACTIVE_CONTENT_EXTENSIONS = /\.(?:html?|xhtml|svg|js|mjs|cjs)$/i;

export function canOpenChatAttachmentInBrowser(attachment: Pick<ChatDocumentAttachment, 'name' | 'mimeType'>): boolean {
  const mimeType = attachment.mimeType?.split(';', 1)[0].trim().toLowerCase();
  return !ACTIVE_CONTENT_MIME_TYPES.has(mimeType || '') && !ACTIVE_CONTENT_EXTENSIONS.test(attachment.name);
}

function triggerDownload(file: File): void {
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url;
  link.download = file.name;
  link.rel = 'noopener';
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL?.(url), 0);
}

function triggerDownloadUrl(url: string, name: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = name || 'attachment';
  link.rel = 'noopener';
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
}

export async function downloadChatAttachment(attachment: AttachmentReference, fallbackUrl?: string): Promise<boolean> {
  // Preview URLs are already local data/blob URLs. Using them directly keeps
  // the download inside the original user gesture, which mobile browsers
  // otherwise lose while waiting for an authenticated fetch.
  if (fallbackUrl) {
    triggerDownloadUrl(fallbackUrl, attachment.name || 'attachment');
    return true;
  }
  const blob = await getChatAttachmentBlob(attachment.storageKey, attachment.mimeType, fallbackUrl);
  if (!blob) return false;
  const file = new File([blob], attachment.name || 'attachment', {
    type: attachment.mimeType || blob.type || 'application/octet-stream',
  });
  if (typeof navigator !== 'undefined' && navigator.share && navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: file.name });
      return true;
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return true;
    }
  }
  triggerDownload(file);
  return true;
}

export async function openChatAttachmentInBrowser(attachment: AttachmentReference, fallbackUrl?: string): Promise<boolean> {
  if (!canOpenChatAttachmentInBrowser(attachment)) return false;
  // Open the existing preview URL synchronously so popup blockers do not
  // reject it after an asynchronous blob fetch.
  if (fallbackUrl) return Boolean(window.open(fallbackUrl, '_blank', 'noopener,noreferrer'));
  const blob = await getChatAttachmentBlob(attachment.storageKey, attachment.mimeType, fallbackUrl);
  if (!blob) return false;
  const url = URL.createObjectURL(blob);
  const opened = window.open(url, '_blank', 'noopener,noreferrer');
  window.setTimeout(() => URL.revokeObjectURL?.(url), 60_000);
  return Boolean(opened);
}

const SYSTEM_APPLICATION_EXTENSIONS = /\.(doc|docx|ppt|pptx|xls|xlsx|odt|ods|odp|rtf)$/i;

export function shouldOpenWithSystemApplication(attachment: Pick<ChatDocumentAttachment, 'name' | 'mimeType'>): boolean {
  return Boolean(
    SYSTEM_APPLICATION_EXTENSIONS.test(attachment.name)
    || attachment.mimeType?.startsWith('application/vnd.')
    || attachment.mimeType === 'application/msword'
    || attachment.mimeType === 'application/rtf',
  );
}

export async function openChatAttachment(storageKey?: string): Promise<boolean> {
  if (!isLocalAuthority() || !storageKey?.startsWith('server:')) return false;
  const attachmentId = storageKey.slice('server:'.length);
  if (!SERVER_ATTACHMENT_ID.test(attachmentId)) return false;
  try {
    const response = await fetch(`${RAG_BASE}/attachments/${attachmentId}/open`, {
      method: 'POST',
      headers: systemRequestHeaders(),
    });
    return response.ok;
  } catch {
    return false;
  }
}
