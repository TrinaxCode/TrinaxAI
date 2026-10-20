import { useEffect, useRef, useState, type ComponentType, type KeyboardEvent } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { MdAutoAwesome, MdCheck, MdChatBubbleOutline, MdExpandMore, MdPsychology, MdSpeed } from 'react-icons/md';
import type { TranslationKey } from '../../i18n/translations';
import type { Translate } from '../chat/types';
import type { AgentModelMode } from './agentTypes';

interface ModeDefinition {
  mode: AgentModelMode;
  label: TranslationKey;
  hint: TranslationKey;
  Icon: ComponentType<{ size?: number; className?: string }>;
}

export const AGENT_MODEL_MODES: readonly ModeDefinition[] = [
  { mode: 'auto', label: 'agentModelAuto', hint: 'agentModelAutoHint', Icon: MdAutoAwesome },
  { mode: 'chat', label: 'agentModelChat', hint: 'agentModelChatHint', Icon: MdChatBubbleOutline },
  { mode: 'deep', label: 'agentModelDeep', hint: 'agentModelDeepHint', Icon: MdPsychology },
  { mode: 'fast', label: 'agentModelFast', hint: 'agentModelFastHint', Icon: MdSpeed },
];

interface OptionListProps {
  modelMode: AgentModelMode;
  /** Concrete model configured for each mode; `auto` has none because the router decides per task. */
  modelNames: Partial<Record<AgentModelMode, string>>;
  onSelect: (mode: AgentModelMode) => void;
  isDark: boolean;
  t: Translate;
  disabled?: boolean;
  label: string;
}

/** Radio-style list shared by the desktop popover and the mobile tools menu. */
export function AgentModelOptions({ modelMode, modelNames, onSelect, isDark, t, disabled = false, label }: OptionListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const move = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    const options = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]:not(:disabled)') ?? []);
    if (!options.length) return;
    event.preventDefault();
    const current = options.findIndex((option) => option === document.activeElement);
    const next = event.key === 'ArrowDown' ? (current + 1) % options.length : (current - 1 + options.length) % options.length;
    options[next].focus();
  };

  return (
    <div ref={listRef} role="radiogroup" aria-label={label} onKeyDown={move} className="flex flex-col gap-0.5">
      {AGENT_MODEL_MODES.map(({ mode, label: modeLabel, hint, Icon }) => {
        const selected = mode === modelMode;
        const modelName = modelNames[mode];
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={selected}
            data-agent-model-option={mode}
            disabled={disabled}
            onClick={() => onSelect(mode)}
            className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-40 ${selected ? isDark ? 'bg-[#168de2]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
          >
            <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${selected ? 'bg-[#006bbd] text-white' : isDark ? 'bg-white/[0.06] text-white/70' : 'bg-gray-100 text-gray-600'}`}>
              <Icon size={17} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{t(modeLabel)}</span>
              <span className={`block truncate text-xs ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{t(hint)}</span>
              {modelName && <span className={`block truncate font-mono text-[11px] ${isDark ? 'text-[#7cc0f0]' : 'text-[#006bbd]'}`}>{modelName}</span>}
            </span>
            {selected && <MdCheck size={16} aria-hidden="true" className={isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]'} />}
          </button>
        );
      })}
    </div>
  );
}

interface PickerProps extends Omit<OptionListProps, 'label'> {
  /** Real model the backend reported for the latest turn. */
  activeModelName: string;
}

export default function AgentModelPicker({ modelMode, modelNames, activeModelName, onSelect, isDark, t, disabled = false }: PickerProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const prefersReducedMotion = useReducedMotion();
  const current = AGENT_MODEL_MODES.find((item) => item.mode === modelMode) ?? AGENT_MODEL_MODES[0];
  const CurrentIcon = current.Icon;

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    const focusTimer = window.setTimeout(() => {
      rootRef.current?.querySelector<HTMLButtonElement>('[role="radio"][aria-checked="true"]')?.focus();
    }, 0);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        data-agent-model-trigger
        onClick={() => setOpen((value) => !value)}
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`${t('agentModel')}: ${t(current.label)}`}
        title={activeModelName ? `${t('agentModelActive')}: ${activeModelName}` : t('agentModel')}
        className={`flex min-h-11 max-w-56 items-center gap-2 rounded-xl border px-2.5 text-sm transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-40 ${isDark ? 'border-white/[0.1] text-white/80 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-100'}`}
      >
        <CurrentIcon size={17} className="shrink-0" />
        <span className="min-w-0 text-left leading-tight">
          <span className="block truncate font-medium">{t(current.label)}</span>
          {activeModelName && <span data-agent-model className={`block max-w-36 truncate font-mono text-[10px] ${isDark ? 'text-[#7cc0f0]' : 'text-[#006bbd]'}`}>{activeModelName}</span>}
        </span>
        <MdExpandMore size={18} aria-hidden="true" className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog"
            aria-label={t('agentModel')}
            initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.96, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -6 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.15, ease: [0.16, 1, 0.3, 1] }}
            className={`absolute right-0 top-full z-50 mt-1.5 w-[min(20rem,calc(100vw-1rem))] rounded-xl border p-1.5 shadow-xl ${isDark ? 'border-white/[0.1] bg-[#101a26] shadow-black/50' : 'border-gray-200 bg-white shadow-gray-300/60'}`}
          >
            <AgentModelOptions
              modelMode={modelMode}
              modelNames={modelNames}
              onSelect={(mode) => { onSelect(mode); setOpen(false); triggerRef.current?.focus(); }}
              isDark={isDark}
              t={t}
              label={t('agentModel')}
            />
            {activeModelName && (
              <p className={`mt-1 border-t px-2.5 pt-2 pb-1 text-xs ${isDark ? 'border-white/[0.08] text-white/60' : 'border-gray-200 text-gray-600'}`}>
                {t('agentModelActive')}: <span className={`font-mono ${isDark ? 'text-[#7cc0f0]' : 'text-[#006bbd]'}`}>{activeModelName}</span>
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
