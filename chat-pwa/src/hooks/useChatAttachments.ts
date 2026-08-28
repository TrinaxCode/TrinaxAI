import { useCallback, useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent, type DragEvent } from 'react';
import { prepareImageForVision, userFacingError, type ChatDocumentAttachment } from '../lib/api';
import { canOpenChatAttachmentInBrowser, downloadChatAttachment, getChatAttachmentUrl, openChatAttachment, openChatAttachmentInBrowser, shouldOpenWithSystemApplication } from '../lib/chatAttachments';
import { filesFromDataTransfer, imageFilesFrom, MAX_ATTACHMENTS_PER_TYPE } from '../lib/attachmentAccept';
import { audioManager } from '../services/audioManager';
import type { TranslationKey } from '../i18n/translations';
import type { PendingImage } from './useChatVoice';
import type { PreviewAttachment } from '../components/chat/AttachmentPreview';

type Translate = (key: TranslationKey) => string;

interface UseChatAttachmentsOptions {
  callMode: boolean;
  processDocumentFiles: (files: File[]) => void | Promise<void>;
  t: Translate;
}

export function useChatAttachments({ callMode, processDocumentFiles, t }: UseChatAttachmentsOptions) {
  const [attachedImages, setAttachedImages] = useState<PendingImage[]>([]);
  const [previewAttachment, setPreviewAttachment] = useState<PreviewAttachment | null>(null);
  const [textPreview, setTextPreview] = useState<string | null>(null);
  const [imageError, setImageError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const clearDragActive = useCallback(() => setDragActive(false), []);

  const processImageFiles = useCallback(async (selected: File[]) => {
    if (!selected.length) return;
    const available = Math.max(0, MAX_ATTACHMENTS_PER_TYPE - attachedImages.length);
    const files = selected.slice(0, available);
    if (!files.length) {
      setImageError(t('chatImagesOmitted').replace('{count}', String(selected.length)));
      return;
    }
    try {
      setImageError('');
      const prepared: PendingImage[] = [];
      let failures = 0;
      for (const file of files) {
        try {
          audioManager.play('file-received');
          prepared.push({ file, dataUrl: await prepareImageForVision(file) });
        } catch {
          failures += 1;
        }
      }
      setAttachedImages((current) => [...current, ...prepared].slice(0, MAX_ATTACHMENTS_PER_TYPE));
      const omitted = selected.length - files.length + failures;
      if (omitted) setImageError(t('chatImagesOmitted').replace('{count}', String(omitted)));
      audioManager.play('file-ready');
    } catch (err: unknown) {
      setImageError(userFacingError(err, 'document_unreadable'));
    }
  }, [attachedImages.length, t]);

  const onPickImage = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    event.target.value = '';
    void processImageFiles(selected);
  }, [processImageFiles]);

  const handleAttachmentFiles = useCallback((files: File[]): boolean => {
    const images = imageFilesFrom(files);
    const documents = files.filter((file) => !file.type.toLowerCase().startsWith('image/'));
    if (images.length) void processImageFiles(images);
    if (documents.length) void processDocumentFiles(documents);
    return images.length > 0 || documents.length > 0;
  }, [processDocumentFiles, processImageFiles]);

  const handlePaste = useCallback((event: ClipboardEvent<HTMLDivElement>) => {
    if (callMode) return;
    const files = filesFromDataTransfer(event.clipboardData);
    if (files.length && handleAttachmentFiles(files)) event.preventDefault();
  }, [callMode, handleAttachmentFiles]);

  const hasDraggedFiles = useCallback((event: DragEvent<HTMLDivElement>) => (
    Array.from(event.dataTransfer.types).includes('Files')
  ), []);

  const handleDragEnter = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (callMode || !hasDraggedFiles(event)) return;
    event.preventDefault();
    setDragActive(true);
  }, [callMode, hasDraggedFiles]);

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (callMode || !hasDraggedFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    setDragActive(true);
  }, [callMode, hasDraggedFiles]);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (!dragActive) return;
    const relatedTarget = event.relatedTarget as Node | null;
    if (relatedTarget && event.currentTarget.contains(relatedTarget)) return;
    setDragActive(false);
  }, [dragActive]);

  const handleDrop = useCallback((event: DragEvent<HTMLDivElement>) => {
    if (callMode || !hasDraggedFiles(event)) return;
    event.preventDefault();
    setDragActive(false);
    handleAttachmentFiles(filesFromDataTransfer(event.dataTransfer));
  }, [callMode, handleAttachmentFiles, hasDraggedFiles]);

  const openStoredAttachment = useCallback(async (attachment: ChatDocumentAttachment, inlineUrl?: string) => {
    const url = inlineUrl || await getChatAttachmentUrl(attachment.storageKey, attachment.mimeType);
    if (url) setPreviewAttachment({ attachment, url });
  }, []);

  const openPreviewAttachment = useCallback(async () => {
    if (!previewAttachment) return false;
    if (shouldOpenWithSystemApplication(previewAttachment.attachment)
      && await openChatAttachment(previewAttachment.attachment.storageKey)) return true;
    return openChatAttachmentInBrowser(previewAttachment.attachment, previewAttachment.url);
  }, [previewAttachment]);

  const downloadPreviewAttachment = useCallback(async () => {
    if (!previewAttachment) return false;
    return downloadChatAttachment(previewAttachment.attachment, previewAttachment.url);
  }, [previewAttachment]);

  useEffect(() => {
    const controller = new AbortController();
    setTextPreview(null);
    if (!previewAttachment) return undefined;
    const isText = previewAttachment.attachment.mimeType?.startsWith('text/')
      || /\.(md|txt|csv|json|xml|html|css|js|ts|tsx|jsx|py|java|c|cpp|h|log)$/i.test(previewAttachment.attachment.name);
    if (!isText) return undefined;
    fetch(previewAttachment.url, { signal: controller.signal })
      .then((response) => response.text())
      .then((text) => setTextPreview(text))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) setTextPreview(null);
      });
    return () => controller.abort();
  }, [previewAttachment]);

  useEffect(() => {
    const url = previewAttachment?.url;
    return () => { if (url?.startsWith('blob:')) URL.revokeObjectURL(url); };
  }, [previewAttachment]);

  const canOpenPreview = Boolean(
    previewAttachment
      && (shouldOpenWithSystemApplication(previewAttachment.attachment)
        || canOpenChatAttachmentInBrowser(previewAttachment.attachment)),
  );

  return {
    attachedImages,
    canOpenPreview,
    clearDragActive,
    dragActive,
    fileInputRef,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    handlePaste,
    imageError,
    onPickImage,
    openPreviewAttachment,
    openStoredAttachment,
    downloadPreviewAttachment,
    previewAttachment,
    setAttachedImages,
    setPreviewAttachment,
    textPreview,
  };
}
