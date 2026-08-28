import type { ChangeEvent, KeyboardEvent, ReactNode, RefObject } from 'react';
import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { MdClose, MdOpenInFull } from 'react-icons/md';
import { useDialogAccessibility } from '../../hooks/useDialogAccessibility';

interface ComposerLayoutProps {
  value: string;
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  placeholder: string;
  name?: string;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  disabled?: boolean;
  isDark: boolean;
  expandLabel: string;
  closeLabel: string;
  leftActions: ReactNode;
  rightActions: ReactNode;
  floatingContent?: ReactNode;
}

const MIN_HEIGHT = 42;
const MAX_HEIGHT = 360;
const EXPAND_THRESHOLD = 96;

function maxEditorHeight(): number {
  return Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, window.innerHeight * 0.5));
}

export default function ComposerLayout({
  value,
  onChange,
  onKeyDown,
  placeholder,
  name,
  inputRef,
  disabled = false,
  isDark,
  expandLabel,
  closeLabel,
  leftActions,
  rightActions,
  floatingContent,
}: ComposerLayoutProps) {
  const shellRef = useRef<HTMLDivElement | null>(null);
  const leftSlotRef = useRef<HTMLDivElement | null>(null);
  const rightSlotRef = useRef<HTMLDivElement | null>(null);
  const expandedInputRef = useRef<HTMLTextAreaElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const shortActionsWidthRef = useRef(0);
  const stackedRef = useRef(false);
  const [stacked, setStacked] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const closeExpanded = useCallback(() => setExpanded(false), []);
  const { dialogRef, onKeyDown: onDialogKeyDown } = useDialogAccessibility(
    expanded,
    closeExpanded,
    closeButtonRef,
  );

  const resizeEditor = useCallback((element: HTMLTextAreaElement | null, compact = false) => {
    if (!element) return;
    if (compact) {
      element.style.height = '24px';
      element.style.maxHeight = '24px';
      element.style.overflowY = 'hidden';
      return;
    }
    const maxHeight = maxEditorHeight();
    element.style.height = 'auto';
    const height = Math.min(Math.max(element.scrollHeight, MIN_HEIGHT), maxHeight);
    element.style.height = `${height}px`;
    element.style.overflowY = element.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }, []);

  const measureLayout = useCallback(() => {
    const element = inputRef.current;
    const shell = shellRef.current;
    const leftSlot = leftSlotRef.current;
    const rightSlot = rightSlotRef.current;
    if (!element || !shell || !leftSlot || !rightSlot) return;

    if (!stackedRef.current) {
      shortActionsWidthRef.current = leftSlot.offsetWidth + rightSlot.offsetWidth;
    }
    const savedWidth = element.style.width;
    const savedFlex = element.style.flex;
    const controlsWidth = shortActionsWidthRef.current;
    const shortWidth = Math.max(96, shell.clientWidth - controlsWidth - 36);
    const computed = window.getComputedStyle(element);
    const lineHeight = Number.parseFloat(computed.lineHeight) || 24;

    // Measure at the compact layout width, not the current full-width width.
    // This prevents a long line from toggling between layouts on every render.
    element.style.width = `${shortWidth}px`;
    element.style.flex = 'none';
    element.style.height = `${lineHeight}px`;
    element.style.overflowY = 'hidden';
    const needsStack = value.length > 0 && (value.includes('\n') || element.scrollHeight > lineHeight + 4);
    element.style.width = savedWidth;
    element.style.flex = savedFlex;
    resizeEditor(element, !needsStack);

    if (needsStack !== stackedRef.current) {
      stackedRef.current = needsStack;
      setStacked(needsStack);
    }
  }, [inputRef, resizeEditor, value]);

  useLayoutEffect(() => {
    measureLayout();
  }, [measureLayout]);

  useLayoutEffect(() => {
    const shell = shellRef.current;
    if (!shell || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => measureLayout());
    observer.observe(shell);
    return () => observer.disconnect();
  }, [measureLayout]);

  useLayoutEffect(() => {
    const element = expandedInputRef.current;
    if (!element) return;
    if (expanded) {
      element.style.height = '100%';
      element.style.maxHeight = 'none';
      element.style.overflowY = 'auto';
      return;
    }
    resizeEditor(element);
  }, [expanded, resizeEditor, value]);

  const editor = (elementRef: RefObject<HTMLTextAreaElement | null>, expandedEditor = false) => (
    <textarea
      data-group-focus
      ref={elementRef}
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      rows={1}
      placeholder={placeholder}
      aria-label={placeholder}
      name={name}
      disabled={disabled}
      className={`block w-full resize-none overflow-y-hidden break-words bg-transparent text-sm leading-6 outline-none ${expandedEditor ? 'h-full min-h-0 flex-1 px-3 py-2' : stacked ? 'min-h-[42px] max-h-[360px] px-3 py-2' : 'h-6 min-h-6 max-h-6 px-0 py-0 leading-6'} ${!expandedEditor && canExpand ? 'pr-14' : ''} ${isDark ? 'text-white placeholder:text-white/30' : 'text-gray-800 placeholder:text-gray-400'}`}
      style={{ maxHeight: expandedEditor ? 'none' : stacked ? `${MAX_HEIGHT}px` : '24px' }}
    />
  );

  const editorSurface = (elementRef: RefObject<HTMLTextAreaElement | null>, expandedEditor = false) => (
    <div className={`relative min-h-0 ${expandedEditor ? 'h-full' : ''}`}>
      {editor(elementRef, expandedEditor)}
    </div>
  );

  const actionRow = (measure = false) => (
    <div className="flex w-full items-center justify-between gap-2">
      <div ref={measure ? leftSlotRef : undefined} className="flex min-w-0 items-center gap-2">{leftActions}</div>
      <div ref={measure ? rightSlotRef : undefined} className="flex shrink-0 items-center gap-2">{rightActions}</div>
    </div>
  );

  const canExpand = stacked && value.trim().length >= EXPAND_THRESHOLD;
  const expandButton = (
    <button
      type="button"
      onClick={() => setExpanded(true)}
      className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl transition-colors ${isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-200 text-gray-500 hover:bg-gray-300 hover:text-gray-700'}`}
      aria-label={expandLabel}
    >
      <MdOpenInFull size={18} />
    </button>
  );

  return (
    <>
      <div ref={shellRef} className="composer-shell relative z-30 w-full">
        {floatingContent}
        <div className={`composer-surface rounded-2xl border transition-[background-color,border-color,height] duration-200 ${stacked ? 'grid grid-cols-1 gap-2 px-2 py-2 sm:px-3' : 'grid h-[52px] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 px-2 py-1 sm:px-3'} ${isDark ? 'border-white/[0.08] bg-white/[0.04] focus-within:border-[#006bbd]/40' : 'border-gray-200 bg-gray-100 focus-within:border-[#006bbd]/40'}`}>
          {!stacked && <div ref={leftSlotRef} className="flex min-w-0 items-center">{leftActions}</div>}
          <div className={`relative min-w-0 ${stacked ? 'w-full' : 'w-full'}`}>
            {canExpand && <div className="absolute right-1 top-1 z-10">{expandButton}</div>}
            {editorSurface(inputRef)}
          </div>
          {!stacked && <div ref={rightSlotRef} className="flex shrink-0 items-center gap-2">{rightActions}</div>}
          {stacked && <div className="w-full shrink-0">{actionRow(true)}</div>}
        </div>
      </div>

      {typeof document !== 'undefined' && createPortal(
        <AnimatePresence>
          {expanded && (
            <motion.div
              data-modal-root
              className="fixed inset-0 z-[80] flex items-center justify-center p-2 sm:p-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
            >
              <div aria-hidden="true" className="absolute inset-0 bg-black/60" onClick={closeExpanded} />
              <motion.div
                ref={dialogRef}
                onKeyDown={onDialogKeyDown}
                initial={{ opacity: 0, y: 24, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 24, scale: 0.97 }}
                transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
                className={`relative z-10 flex h-[calc(100dvh-1rem)] max-h-[calc(100dvh-1rem)] w-full max-w-[96rem] flex-col overscroll-contain rounded-2xl border p-3 shadow-2xl sm:h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-2rem)] sm:p-5 ${isDark ? 'border-white/[0.1] bg-[#111]' : 'border-gray-200 bg-white'}`}
                role="dialog"
                aria-modal="true"
                aria-label={expandLabel}
              >
                <div className={`relative flex min-h-0 flex-1 flex-col rounded-xl border px-2 py-1 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}>
                  <button ref={closeButtonRef} type="button" onClick={closeExpanded} className={`absolute right-2 top-2 z-10 grid h-10 w-10 place-items-center rounded-xl ${isDark ? 'bg-black/30 text-white/60 hover:bg-white/[0.08] hover:text-white' : 'bg-white/80 text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`} aria-label={closeLabel} title={closeLabel}><MdClose size={20} /></button>
                  <div className="min-h-0 flex-1 overflow-hidden">{editorSurface(expandedInputRef, true)}</div>
                  <div className="mt-2 pt-2">{actionRow()}</div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}
