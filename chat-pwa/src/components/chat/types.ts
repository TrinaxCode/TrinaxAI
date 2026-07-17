import type { TranslationKey } from '../../i18n/translations';

export type Translate = (key: TranslationKey) => string;

export interface AttachedDocument {
  name: string;
  size: number;
  content: string;
  file: File;
  truncated: boolean;
}

export interface ChatPrompt {
  name: string;
  text: string;
  builtin?: boolean;
  kind?: BuiltinKind;
}

export type BuiltinKind =
  | 'navigate_settings'
  | 'navigate_indexing'
  | 'navigate_browser'
  | 'navigate_memory'
  | 'navigate_docs'
  | 'deep_research'
  | 'summarize'
  | 'export_markdown'
  | 'noop';

export interface BuiltinCommand extends ChatPrompt {
  builtin: true;
  kind: BuiltinKind;
  hint: string;
}

export interface QuickChipDef {
  labelKey: TranslationKey;
  icon: string;
  kind: 'navigate' | 'slash' | 'prompt' | 'callMode' | 'pickImage' | 'pickFile' | 'toggleResearch';
  page?: string;
  command?: string;
  promptKey?: TranslationKey;
}

export interface DisplayChip {
  label: string;
  icon: string;
  action: () => void;
  idx: number;
}
