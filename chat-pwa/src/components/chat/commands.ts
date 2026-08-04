import type { BuiltinCommand, QuickChipDef } from './types';
import { translations, type TranslationKey } from '../../i18n/translations';

const BUILTIN_COMMANDS: BuiltinCommand[] = [
  { name: 'index', text: '', builtin: true, kind: 'navigate_indexing', hint: '' },
  { name: 'browse', text: '', builtin: true, kind: 'navigate_browser', hint: '' },
  { name: 'memory', text: '', builtin: true, kind: 'navigate_memory', hint: '' },
  { name: 'watch', text: '', builtin: true, kind: 'navigate_indexing', hint: '' },
  { name: 'research', text: '', builtin: true, kind: 'deep_research', hint: '' },
  { name: 'summarize', text: '', builtin: true, kind: 'summarize', hint: '' },
  { name: 'export', text: '', builtin: true, kind: 'export_markdown', hint: '' },
  { name: 'sources', text: '', builtin: true, kind: 'navigate_browser', hint: '' },
];

const BUILTIN_HINT_KEYS: Record<string, TranslationKey> = {
  index: 'builtinHint_index',
  browse: 'builtinHint_browse',
  memory: 'builtinHint_memory',
  watch: 'builtinHint_watch',
  research: 'builtinHint_research',
  summarize: 'builtinHint_summarize',
  resumir: 'builtinHint_summarize',
  export: 'builtinHint_export',
  sources: 'builtinHint_sources',
};

export function getBuiltinHint(name: string, lang: 'es' | 'en'): string {
  const key = BUILTIN_HINT_KEYS[name];
  return key ? translations[lang][key] : '';
}

export function localizedBuiltins(lang: 'es' | 'en'): BuiltinCommand[] {
  return BUILTIN_COMMANDS.map((command) => command.kind === 'summarize'
    ? { ...command, name: lang === 'es' ? 'resumir' : 'summarize' }
    : command);
}

export function findBuiltin(name: string, lang: 'es' | 'en'): BuiltinCommand | undefined {
  const normalized = name.toLowerCase();
  return localizedBuiltins(lang).find((command) => command.name === normalized);
}

export const QUICK_CHIP_POOL: QuickChipDef[] = [
  { labelKey: 'quickChipIdeas', icon: '💡', kind: 'prompt', promptKey: 'quickChipIdeasPrompt' },
  { labelKey: 'quickChipWrite', icon: '✍️', kind: 'prompt', promptKey: 'quickChipWritePrompt' },
  { labelKey: 'quickChipPlan', icon: '🗓️', kind: 'prompt', promptKey: 'quickChipPlanPrompt' },
  { labelKey: 'quickChipLearn', icon: '📚', kind: 'prompt', promptKey: 'quickChipLearnPrompt' },
  { labelKey: 'quickChipSummarizeText', icon: '📝', kind: 'prompt', promptKey: 'quickChipSummarizeTextPrompt' },
  { labelKey: 'quickChipTranslateText', icon: '🌐', kind: 'prompt', promptKey: 'quickChipTranslateTextPrompt' },
  { labelKey: 'quickChipCompare', icon: '⚖️', kind: 'prompt', promptKey: 'quickChipComparePrompt' },
  { labelKey: 'quickChipOrganize', icon: '✅', kind: 'prompt', promptKey: 'quickChipOrganizePrompt' },
  { labelKey: 'quickChipTrip', icon: '🧳', kind: 'prompt', promptKey: 'quickChipTripPrompt' },
  { labelKey: 'quickChipDecision', icon: '🎯', kind: 'prompt', promptKey: 'quickChipDecisionPrompt' },
];
