import { useEffect, useState } from 'react';
import { MdAdd, MdDelete } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import { syncSharedStateOnce } from '../lib/sharedState';
import ConfirmModal from './ConfirmModal';
import { useToast } from './Toast';

interface CustomPrompt {
  name: string;
  text: string;
}

interface Props {
  isDark: boolean;
  sectionBg: string;
  textValue: string;
  textPlaceholder: string;
  borderFocus: string;
}

const PROMPTS_KEY = 'tc-prompts';
const LEGACY_PROMPT_KEYS = ['tc-ollama-prompts', 'tc-rag-prompts'];

function loadPrompts(): CustomPrompt[] {
  try {
    const current = JSON.parse(localStorage.getItem(PROMPTS_KEY) || 'null');
    if (Array.isArray(current) && current.length) {
      return current.filter((prompt) => prompt?.name && prompt.name !== 'system');
    }
    const legacy = LEGACY_PROMPT_KEYS.flatMap((key) => {
      try {
        const value = JSON.parse(localStorage.getItem(key) || '[]');
        return Array.isArray(value) ? value : [];
      } catch {
        return [];
      }
    });
    const unique = new Map<string, CustomPrompt>();
    legacy.forEach((prompt) => {
      if (prompt?.name && prompt.name !== 'system') {
        unique.set(String(prompt.name), { name: String(prompt.name), text: String(prompt.text || '') });
      }
    });
    return [...unique.values()];
  } catch {
    return [];
  }
}

export default function SettingsPrompts({ isDark, sectionBg, textValue, textPlaceholder, borderFocus }: Props) {
  const { t } = useI18n();
  const toast = useToast();
  const [prompts, setPrompts] = useState<CustomPrompt[]>(loadPrompts);
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [deleteName, setDeleteName] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem(PROMPTS_KEY, JSON.stringify(prompts));
    const id = window.setTimeout(() => { void syncSharedStateOnce(1200); }, 450);
    return () => window.clearTimeout(id);
  }, [prompts]);

  const add = () => {
    const normalized = name.trim().toLowerCase().replace(/\s+/g, '-');
    if (!normalized || !text.trim()) return;
    if (prompts.some((prompt) => prompt.name === normalized)) {
      toast.toast(t('promptExists'), 'warning');
      return;
    }
    setPrompts((items) => [...items, { name: normalized, text: text.trim() }]);
    setName('');
    setText('');
    toast.toast(t('promptAdded'), 'success');
  };

  const update = (promptName: string, value: string) => {
    setPrompts((items) => items.map((prompt) => prompt.name === promptName ? { ...prompt, text: value } : prompt));
  };

  const remove = () => {
    if (!deleteName || deleteName === 'system') return;
    setPrompts((items) => items.filter((prompt) => prompt.name !== deleteName));
    setDeleteName(null);
    toast.toast(t('promptDeleted'), 'info');
  };

  return (
    <>
      <section className="space-y-4">
        {prompts.map((prompt) => (
          <div key={prompt.name} className={`${sectionBg} space-y-2 rounded-xl p-4`}>
            <div className="flex items-center justify-between">
              <span className={`text-[10px] font-mono ${isDark ? 'text-white/30' : 'text-gray-400'}`}>/{prompt.name}</span>
              <button type="button" onClick={() => setDeleteName(prompt.name)} className={`p-1 ${isDark ? 'text-white/20' : 'text-gray-300'} hover:text-red-400`} aria-label={t('deletePrompt')} title={t('deletePrompt')}>
                <MdDelete size={14} />
              </button>
            </div>
            <textarea aria-label={`${t('promptText')} | ${prompt.name}`} value={prompt.text} onChange={(event) => update(prompt.name, event.target.value)} rows={3} className={`w-full resize-none rounded-lg border bg-transparent px-3 py-2 text-sm outline-none ${textValue} ${textPlaceholder} ${isDark ? 'border-white/[0.06]' : 'border-gray-200'} ${borderFocus}`} />
          </div>
        ))}
        <div className={`space-y-3 rounded-xl border border-dashed p-4 ${isDark ? 'border-white/[0.08]' : 'border-gray-300'}`}>
          <input aria-label={t('promptName')} value={name} onChange={(event) => setName(event.target.value)} placeholder={t('promptName')} maxLength={30} className={`w-full bg-transparent text-sm outline-none ${textValue} ${textPlaceholder}`} />
          <textarea aria-label={t('promptText')} value={text} onChange={(event) => setText(event.target.value)} placeholder={t('promptText')} rows={2} className={`w-full resize-none rounded-lg border bg-transparent px-3 py-2 text-sm outline-none ${textValue} ${textPlaceholder} ${isDark ? 'border-white/[0.06]' : 'border-gray-200'} ${borderFocus}`} />
          <button type="button" onClick={add} className="flex items-center gap-1.5 rounded-lg bg-[#006bbd]/15 px-3 py-1.5 text-xs text-[#006bbd] hover:bg-[#006bbd]/25">
            <MdAdd size={14} /> {t('addPrompt')}
          </button>
        </div>
      </section>
      <ConfirmModal
        open={deleteName !== null}
        title={t('deletePrompt')}
        message={t('promptDeleteConfirm').replace('{name}', deleteName || '')}
        confirmLabel={t('delete')}
        danger
        onConfirm={remove}
        onCancel={() => setDeleteName(null)}
      />
    </>
  );
}
