import { memo } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import type { ChatEngine } from '../lib/api';

interface ToggleSwitchProps {
  engine: ChatEngine;
  onChange: (engine: ChatEngine) => void;
}

const ToggleSwitch = memo(function ToggleSwitch({ engine, onChange }: ToggleSwitchProps) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const isRag = engine === 'rag';
  const activeText = 'text-[#006bbd]';
  const inactiveText = isDark
    ? 'text-white/40 hover:text-white/60'
    : 'text-gray-600 hover:text-gray-900';

  return (
    <div className="flex items-center gap-0.5 sm:gap-1.5">
      <button
        onClick={() => onChange('ollama')}
        aria-pressed={!isRag}
        className={`text-[11px] font-medium tracking-wide whitespace-nowrap px-1 sm:px-2 py-1 rounded-lg transition-[background-color,color,opacity,transform] active:scale-95 ${
          !isRag ? activeText : inactiveText
        }`}
      >
        {t('ollamaEngine')}
      </button>

      <button
        role="switch"
        aria-checked={isRag}
        aria-label={t('ragEngine')}
        onClick={() => onChange(isRag ? 'ollama' : 'rag')}
        className="relative flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full transition-transform duration-300 active:scale-95"
      >
        <span className={`relative block h-4 w-8 rounded-full transition-[background-color,box-shadow] duration-300 sm:h-5 sm:w-10 ${isRag ? 'bg-[#006bbd] shadow-[0_0_10px_rgba(0,107,189,0.4)]' : isDark ? 'bg-white/[0.15]' : 'bg-gray-400'}`}>
          <span
            className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow-md transition-[left] duration-300 sm:top-1 ${
              isRag ? 'left-[calc(100%-0.875rem)] sm:left-[calc(100%-1rem)]' : 'left-0.5'
            }`}
          />
        </span>
      </button>

      <button
        onClick={() => onChange('rag')}
        aria-pressed={isRag}
        className={`text-[11px] font-medium tracking-wide whitespace-nowrap px-1 sm:px-2 py-1 rounded-lg transition-[background-color,color,opacity] ${
          isRag ? activeText : inactiveText
        }`}
      >
        {t('ragEngine')}
      </button>
    </div>
  );
});
export default ToggleSwitch;
