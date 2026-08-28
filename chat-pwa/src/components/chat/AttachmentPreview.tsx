import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { MdClose } from 'react-icons/md';
import type { ChatDocumentAttachment } from '../../lib/api';
import { useI18n } from '../../i18n/I18nContext';
import { useDialogAccessibility } from '../../hooks/useDialogAccessibility';

export interface PreviewAttachment {
  attachment: ChatDocumentAttachment;
  url: string;
}

function textPreviewDocument(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0;padding:16px;background:#fff;color:#202124;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body>${escaped}</body></html>`;
}

function isTextAttachment(attachment: ChatDocumentAttachment): boolean {
  return Boolean(attachment.mimeType?.startsWith('text/') || /\.(md|txt|csv|json|xml|html|css|js|ts|tsx|jsx|py|java|c|cpp|h|log)$/i.test(attachment.name));
}

function isRasterImageAttachment(attachment: ChatDocumentAttachment): boolean {
  return Boolean(
    (attachment.kind === 'image' || attachment.mimeType?.startsWith('image/'))
    && attachment.mimeType !== 'image/svg+xml'
    && !/\.svg$/i.test(attachment.name),
  );
}

interface AttachmentPreviewProps {
  preview: PreviewAttachment | null;
  textPreview: string | null;
  isDark: boolean;
  isMobile: boolean;
  canOpen?: boolean;
  onOpen: () => Promise<boolean>;
  onDownload: () => Promise<boolean>;
  onClose: () => void;
}

export default function AttachmentPreview({ preview, textPreview, isDark, isMobile, canOpen = true, onOpen, onDownload, onClose }: AttachmentPreviewProps) {
  const { t } = useI18n();
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionFailed, setActionFailed] = useState(false);
  const { dialogRef, onKeyDown } = useDialogAccessibility(Boolean(preview), onClose, closeButtonRef);
  useEffect(() => {
    setActionBusy(false);
    setActionFailed(false);
  }, [preview]);
  const runAction = async (action: () => Promise<boolean>) => {
    setActionBusy(true);
    setActionFailed(false);
    try {
      setActionFailed(!(await action()));
    } catch {
      setActionFailed(true);
    } finally {
      setActionBusy(false);
    }
  };
  if (typeof document === 'undefined') return null;
  return createPortal(
    <AnimatePresence>
      {preview && (
        <motion.div
          data-modal-root
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.94, y: 18 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.94, y: 18 }}
            className={`relative flex max-h-[calc(100dvh_-_2rem)] w-full max-w-5xl flex-col overflow-hidden rounded-2xl ${isDark ? 'bg-[#111]' : 'bg-white'}`}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={onKeyDown}
            role="dialog"
            aria-modal="true"
            aria-label={preview.attachment.name}
          >
            <div className={`flex items-center justify-between border-b px-4 py-3 text-sm ${isDark ? 'border-white/[0.08] text-white/80' : 'border-gray-200 text-gray-800'}`}>
              <span className="min-w-0 truncate">{preview.attachment.name}</span>
              <div className="flex items-center gap-2">
                {canOpen && <button type="button" onClick={() => void runAction(onOpen)} disabled={actionBusy} className="rounded-lg border border-[#006bbd] px-3 py-1.5 text-xs text-[#006bbd] disabled:opacity-50">{t('openAttachment')}</button>}
                <button type="button" onClick={() => void runAction(onDownload)} disabled={actionBusy} className="rounded-lg bg-[#006bbd] px-3 py-1.5 text-xs text-white disabled:opacity-50">{t('download')}</button>
                <button ref={closeButtonRef} type="button" onClick={onClose} className="rounded-lg p-1" aria-label={t('close')}><MdClose size={20} /></button>
              </div>
            </div>
            {preview.attachment.localOnly && <p className="border-b border-amber-400/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-700 dark:text-amber-200">{t('chatAttachmentLocalOnly')}</p>}
            {actionFailed && <p role="alert" className="border-b border-red-400/30 bg-red-500/10 px-4 py-2 text-xs text-red-700 dark:text-red-200">{t('attachmentActionFailed')}</p>}
            <div className="min-h-0 flex-1 overflow-auto p-3">
              {isRasterImageAttachment(preview.attachment) ? (
                <img src={preview.url} alt={preview.attachment.name} width={1280} height={720} className="mx-auto h-auto w-auto max-h-[calc(100dvh_-_9rem)] max-w-full object-contain" />
              ) : isTextAttachment(preview.attachment) ? (
                <iframe title={preview.attachment.name} srcDoc={textPreview === null ? '' : textPreviewDocument(textPreview)} className="h-[calc(100dvh_-_9rem)] w-full rounded-lg bg-white" />
              ) : (preview.attachment.mimeType === 'application/pdf' || preview.attachment.name.toLowerCase().endsWith('.pdf')) && !isMobile ? (
                <object data={preview.url} type="application/pdf" className="h-[calc(100dvh_-_9rem)] w-full rounded-lg">
                  <iframe title={preview.attachment.name} src={preview.url} className="h-full w-full" />
                </object>
              ) : preview.attachment.mimeType === 'application/pdf' || preview.attachment.name.toLowerCase().endsWith('.pdf') ? (
                <div className={`p-6 text-center text-sm ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{t('mobileAttachmentHint')}</div>
              ) : (
                <div className={`p-6 text-center text-sm ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{t('downloadFileToOpen')}</div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
