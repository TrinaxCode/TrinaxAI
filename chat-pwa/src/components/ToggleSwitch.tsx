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
  const activeText = isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]';
  const inactiveText = isDark
    ? 'text-white/70 hover:text-white'
    : 'text-gray-600 hover:text-gray-900';

  return (
    <div className="flex items-center gap-0.5 sm:gap-1.5">
      <button
        type="button"
        onClick={() => onChange('ollama')}
        aria-pressed={!isRag}
        className={`min-h-11 whitespace-nowrap rounded-lg px-1 text-xs font-medium tracking-wide transition-[background-color,color,opacity,transform] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95 sm:px-2 ${
          !isRag ? activeText : inactiveText
        }`}
      >
        {t('ollamaEngine')}
      </button>

      <button
        type="button"
        role="switch"
        aria-checked={isRag}
        aria-label={t('ragEngine')}
        onClick={() => onChange(isRag ? 'ollama' : 'rag')}
        className="relative flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full transition-transform duration-300 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95"
      >
        <span className={`relative block h-4 w-8 rounded-full transition-[background-color,box-shadow] duration-300 sm:h-5 sm:w-10 ${isRag ? 'bg-[#006bbd] shadow-[0_0_10px_rgba(0,107,189,0.4)]' : isDark ? 'bg-white/[0.15]' : 'bg-gray-400'}`}>
          <span
            className={`absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-white shadow-md transition-transform duration-300 sm:left-[3px] sm:top-[3px] sm:h-3.5 sm:w-3.5 ${
              isRag ? 'translate-x-4 sm:translate-x-5' : 'translate-x-0'
            }`}
          />
        </span>
      </button>

      <button
        type="button"
        onClick={() => onChange('rag')}
        aria-pressed={isRag}
        className={`min-h-11 whitespace-nowrap rounded-lg px-1 text-xs font-medium tracking-wide transition-[background-color,color,opacity] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] sm:px-2 ${
          isRag ? activeText : inactiveText
        }`}
      >
        {t('ragEngine')}
      </button>
    </div>
  );
});
export default ToggleSwitch;
