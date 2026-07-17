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
  const activeText = 'bg-[#006bbd]/20 text-[#006bbd]';
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
        className={`relative w-8 h-4 sm:w-10 sm:h-5 rounded-full transition-[background-color,box-shadow,transform] duration-300 active:scale-95 shrink-0 ${
          isRag ? 'bg-[#006bbd] shadow-[0_0_10px_rgba(0,107,189,0.4)]' : isDark ? 'bg-white/[0.15]' : 'bg-gray-400'
        }`}
      >
        <div
          className={`absolute top-0.5 sm:top-1 w-3 h-3 rounded-full bg-white shadow-md
                      transition-transform duration-300 ${
                        isRag ? 'translate-x-4 sm:translate-x-6' : 'translate-x-0.5 sm:translate-x-1'
                      }`}
        />
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
