import { RAG_BASE, type ChatDocumentAttachment } from './api';

const DB_NAME = 'trinaxai-chat-files';
const STORE_NAME = 'files';

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
    const response = await fetch(`${RAG_BASE}/attachments`, { method: 'POST', body: form });
    if (!response.ok) throw new Error(`Attachment upload failed: ${response.status}`);
    const stored = await response.json() as {
      id: string;
      storage_key: string;
      name: string;
      size: number;
      mime_type: string;
    };
    return {
      id: stored.id,
      storageKey: stored.storage_key,
      name: stored.name || file.name,
      size: stored.size ?? file.size,
      mimeType: stored.mime_type || file.type || 'application/octet-stream',
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
  return { id, storageKey: id, name: file.name, size: file.size, mimeType: file.type || 'application/octet-stream', kind };
}

export async function getChatAttachmentUrl(storageKey?: string, mimeType?: string): Promise<string | null> {
  if (!storageKey) return null;
  if (storageKey.startsWith('server:')) {
    const attachmentId = storageKey.slice('server:'.length);
    if (/^[0-9a-f]{32}$/.test(attachmentId)) {
      return `${RAG_BASE}/attachments/${attachmentId}`;
    }
    return null;
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
    const typedBlob = mimeType && blob.type !== mimeType ? new Blob([blob], { type: mimeType }) : blob;
    return URL.createObjectURL(typedBlob);
  } catch {
    return null;
  }
}
