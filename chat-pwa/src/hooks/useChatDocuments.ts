import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react';
import { extractDocumentText, getIndexJob, indexableFilesFrom, startFolderIndex, type ChatMessage, type Collection } from '../lib/api';
import { appendAttachmentSelection, MAX_ATTACHMENTS_PER_TYPE } from '../lib/attachmentAccept';
import { getChatAttachmentUrl } from '../lib/chatAttachments';
import { audioManager } from '../services/audioManager';
import { userFacingError } from '../lib/api';
import type { TranslationKey } from '../i18n/translations';
import type { AttachedDocument } from '../components/chat/types';

const DOC_MAX_CHARS = 80_000;
const DOC_TOTAL_MAX_CHARS = 90_000;
const DOC_MAX_FILES = MAX_ATTACHMENTS_PER_TYPE;

type Translate = (key: TranslationKey) => string;

interface UseChatDocumentsOptions {
  collections: Collection[];
  initialCollectionId: string;
  t: Translate;
}

export function useChatDocuments({ collections, initialCollectionId, t }: UseChatDocumentsOptions) {
  const [docUploadStatus, setDocUploadStatus] = useState('');
  const [docConvertProgress, setDocConvertProgress] = useState<{ file: string; progress: number } | null>(null);
  const [attachedDocs, setAttachedDocs] = useState<AttachedDocument[]>([]);
  const [docIndexCollectionId, setDocIndexCollectionId] = useState(initialCollectionId);
  const docInputRef = useRef<HTMLInputElement>(null);
  const docIndexAbortRef = useRef<AbortController | null>(null);
  const docStatusTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (collections.length && !collections.some((item) => item.id === docIndexCollectionId)) {
      setDocIndexCollectionId(collections[0]?.id || 'default');
    }
  }, [collections, docIndexCollectionId]);

  useEffect(() => () => {
    docIndexAbortRef.current?.abort();
    if (docStatusTimerRef.current !== null) window.clearTimeout(docStatusTimerRef.current);
  }, []);

  const indexAttachedDocs = useCallback(async () => {
    if (!attachedDocs.length) return;
    docIndexAbortRef.current?.abort();
    const controller = new AbortController();
    docIndexAbortRef.current = controller;
    const deadline = Date.now() + 10 * 60_000;
    const files = attachedDocs.map((doc) => doc.file);
    const collectionName = collections.find((item) => item.id === docIndexCollectionId)?.name || t('generalCollection');
    setDocUploadStatus(t('chatUploadStarting').replace('{collection}', collectionName));
    try {
      const started = await startFolderIndex(files, { collectionId: docIndexCollectionId, signal: controller.signal });
      if (!started.job_id) {
        setDocUploadStatus(t('chatUploadQueued').replace('{count}', String(started.saved)));
        return;
      }
      let done = false;
      while (!done) {
        if (Date.now() >= deadline) throw new Error(t('indexPhaseTimeout'));
        await new Promise<void>((resolve, reject) => {
          const onAbort = () => {
            window.clearTimeout(timer);
            reject(new DOMException('Index polling cancelled', 'AbortError'));
          };
          const timer = window.setTimeout(() => {
            controller.signal.removeEventListener('abort', onAbort);
            resolve();
          }, 1100);
          controller.signal.addEventListener('abort', onAbort, { once: true });
        });
        const job = await getIndexJob(started.job_id, controller.signal);
        if (job.status === 'completed') {
          setDocUploadStatus(t('chatUploadDone').replace('{count}', String(job.saved)));
          done = true;
        } else if (job.status === 'failed') {
          setDocUploadStatus(job.error ? userFacingError(new Error(job.error), 'document_unreadable') : t('chatUploadFailed'));
          done = true;
        } else if (job.status === 'cancelled') {
          setDocUploadStatus(t('indexCancelled'));
          done = true;
        } else {
          setDocUploadStatus(`${t('indexing')} ${job.progress}%`);
        }
      }
      docStatusTimerRef.current = window.setTimeout(() => {
        docStatusTimerRef.current = null;
        setDocUploadStatus('');
      }, 4500);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setDocUploadStatus(userFacingError(err, 'document_unreadable'));
    } finally {
      if (docIndexAbortRef.current === controller) docIndexAbortRef.current = null;
    }
  }, [attachedDocs, collections, docIndexCollectionId, t]);

  const processDocumentFiles = useCallback(async (selected: File[]) => {
    if (!selected.length) return;
    const files = indexableFilesFrom(selected);
    if (!files.length) {
      setDocUploadStatus(t('chatUploadNoFiles'));
      return;
    }
    try {
      audioManager.play('file-processing');
      let remaining = DOC_TOTAL_MAX_CHARS;
      const docs: AttachedDocument[] = [];
      const available = Math.max(0, DOC_MAX_FILES - attachedDocs.length);
      const selectedDocs = files.slice(0, available);
      const failures: string[] = [];
      for (let index = 0; index < selectedDocs.length; index += 1) {
        const file = selectedDocs[index];
        setDocUploadStatus(t('chatDocConverting').replace('{file}', file.name));
        setDocConvertProgress({ file: file.name, progress: Math.max(1, Math.round((index / selectedDocs.length) * 100)) });
        let extracted;
        try {
          extracted = await extractDocumentText(file, {
            onUploadProgress: (progress) => {
              const current = Math.min(95, Math.round(((index * 100) + progress) / selectedDocs.length));
              setDocConvertProgress({ file: file.name, progress: current });
            },
          });
        } catch (err: unknown) {
          failures.push(`${file.name}: ${userFacingError(err, 'document_unreadable')}`);
          continue;
        }
        const raw = extracted.text;
        const room = Math.max(0, remaining);
        const content = raw.slice(0, Math.min(DOC_MAX_CHARS, room));
        remaining -= content.length;
        docs.push({
          name: file.name,
          size: file.size,
          content,
          file,
          truncated: extracted.truncated || content.length < raw.length,
        });
        if (remaining <= 0) break;
      }
      setDocConvertProgress(null);
      setAttachedDocs((current) => appendAttachmentSelection(current, docs, DOC_MAX_FILES));
      audioManager.play('file-ready');
      const omitted = Math.max(0, files.length - selectedDocs.length) + failures.length;
      setDocUploadStatus(
        t('chatDocsAttached').replace('{count}', String(docs.length))
        + (omitted ? ` ${t('chatDocsOmitted').replace('{count}', String(omitted))}` : '')
        + (failures.length ? ` ${failures[0]}` : ''),
      );
    } catch (err: unknown) {
      setDocConvertProgress(null);
      setDocUploadStatus(userFacingError(err, 'document_unreadable'));
    }
  }, [attachedDocs.length, t]);

  const onPickDocs = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    event.target.value = '';
    void processDocumentFiles(selected);
  }, [processDocumentFiles]);

  const rebuildStoredDocumentContext = useCallback(async (message: ChatMessage) => {
    const attachments = (message.documentAttachments ?? [])
      .filter((attachment) => attachment.kind === 'document' && attachment.storageKey)
      .slice(0, DOC_MAX_FILES);
    if (!attachments.length) return '';
    let remaining = DOC_TOTAL_MAX_CHARS;
    const blocks: string[] = [];
    for (const attachment of attachments) {
      if (remaining <= 0) break;
      let url: string | null = null;
      try {
        url = await getChatAttachmentUrl(attachment.storageKey, attachment.mimeType);
        if (!url) continue;
        const response = await fetch(url);
        if (!response.ok) continue;
        const blob = await response.blob();
        const file = new File([blob], attachment.name, {
          type: attachment.mimeType || blob.type || 'application/octet-stream',
        });
        const extracted = await extractDocumentText(file);
        const content = extracted.text.slice(0, Math.min(DOC_MAX_CHARS, remaining));
        remaining -= content.length;
        if (content) {
          blocks.push(
            `\n\n[Archivo adjunto temporal: ${attachment.name}${attachment.truncated || extracted.truncated ? ' (truncado)' : ''}]\n`
            + `\`\`\`text\n${content}\n\`\`\``,
          );
        }
      } catch {
        // Older local-only attachments may no longer be reopenable.
      } finally {
        if (url?.startsWith('blob:')) URL.revokeObjectURL(url);
      }
    }
    return blocks.join('');
  }, []);

  const clearAttachedDocs = useCallback(() => setAttachedDocs([]), []);

  return {
    attachedDocs,
    clearAttachedDocs,
    docConvertProgress,
    docIndexCollectionId,
    docInputRef,
    docUploadStatus,
    indexAttachedDocs,
    onPickDocs,
    processDocumentFiles,
    rebuildStoredDocumentContext,
    setDocUploadStatus,
    setDocIndexCollectionId,
  };
}
