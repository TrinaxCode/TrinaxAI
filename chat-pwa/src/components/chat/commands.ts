import type { BuiltinCommand, QuickChipDef } from './types';

export const BUILTIN_COMMANDS: BuiltinCommand[] = [
  { name: 'index', text: '', builtin: true, kind: 'navigate_indexing', hint: 'Ajustes → Indexar carpeta' },
  { name: 'browse', text: '', builtin: true, kind: 'navigate_browser', hint: 'Knowledge Browser' },
  { name: 'memory', text: '', builtin: true, kind: 'navigate_memory', hint: 'Notas persistentes' },
  { name: 'watch', text: '', builtin: true, kind: 'navigate_indexing', hint: 'Watcher de archivos' },
  { name: 'research', text: '', builtin: true, kind: 'deep_research', hint: 'Multi-pass deep research' },
  { name: 'summarize', text: '', builtin: true, kind: 'summarize', hint: 'Resumir conversación' },
  { name: 'export', text: '', builtin: true, kind: 'export_markdown', hint: 'Exportar como Markdown' },
  { name: 'sources', text: '', builtin: true, kind: 'navigate_browser', hint: 'Ver fuentes indexadas' },
];

export function getBuiltinHint(name: string, lang: 'es' | 'en'): string {
  const hints: Record<string, { es: string; en: string }> = {
    index: { es: 'Ajustes → Indexar carpeta', en: 'Settings → Index folder' },
    browse: { es: 'Navegador de conocimiento', en: 'Knowledge Browser' },
    memory: { es: 'Notas persistentes', en: 'Persistent notes' },
    watch: { es: 'Watcher de archivos', en: 'File watcher' },
    research: { es: 'Investigación profunda', en: 'Multi-pass deep research' },
    summarize: { es: 'Resumir conversación', en: 'Summarize conversation' },
    resumir: { es: 'Resumir conversación', en: 'Summarize conversation' },
    export: { es: 'Descargar chat (MD, PDF, Word)', en: 'Download chat (MD, PDF, Word)' },
    sources: { es: 'Ver fuentes indexadas', en: 'View indexed sources' },
  };
  return hints[name]?.[lang] ?? '';
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
