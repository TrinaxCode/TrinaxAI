import { useRef } from 'react';
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

interface AttachmentPreviewProps {
  preview: PreviewAttachment | null;
  textPreview: string | null;
  isDark: boolean;
  onClose: () => void;
}

export default function AttachmentPreview({ preview, textPreview, isDark, onClose }: AttachmentPreviewProps) {
  const { t } = useI18n();
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const { dialogRef, onKeyDown } = useDialogAccessibility(Boolean(preview), onClose, closeButtonRef);
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
                <a href={preview.url} download={preview.attachment.name} className="rounded-lg bg-[#006bbd] px-3 py-1.5 text-xs text-white">{t('download')}</a>
                <button ref={closeButtonRef} type="button" onClick={onClose} className="rounded-lg p-1" aria-label={t('close')}><MdClose size={20} /></button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-3">
              {(preview.attachment.kind === 'image' || preview.attachment.mimeType?.startsWith('image/')) ? (
                <img src={preview.url} alt={preview.attachment.name} width={1280} height={720} className="mx-auto h-auto w-auto max-h-[calc(100dvh_-_9rem)] max-w-full object-contain" />
              ) : isTextAttachment(preview.attachment) ? (
                <iframe title={preview.attachment.name} srcDoc={textPreview === null ? '' : textPreviewDocument(textPreview)} className="h-[calc(100dvh_-_9rem)] w-full rounded-lg bg-white" />
              ) : preview.attachment.mimeType === 'application/pdf' || preview.attachment.name.toLowerCase().endsWith('.pdf') ? (
                <object data={preview.url} type="application/pdf" className="h-[calc(100dvh_-_9rem)] w-full rounded-lg">
                  <iframe title={preview.attachment.name} src={preview.url} className="h-full w-full" />
                  <a href={preview.url} download={preview.attachment.name}>{t('download')}</a>
                </object>
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
