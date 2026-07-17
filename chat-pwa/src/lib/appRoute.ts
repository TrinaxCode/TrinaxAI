export type AppPage = 'chat' | 'settings' | 'docs' | 'browser' | 'agent';
export type SettingsSection = 'general' | 'indexing' | 'prompts' | 'memory' | 'stats';

export interface AppRoute {
  page: AppPage;
  chatId?: string;
  settingsSection?: SettingsSection;
}

const SETTINGS_SECTIONS = new Set<SettingsSection>([
  'general',
  'indexing',
  'prompts',
  'memory',
  'stats',
]);

function safeDecode(value?: string): string | undefined {
  if (!value) return undefined;
  try { return decodeURIComponent(value); } catch { return undefined; }
}

/** Parse canonical `#/…` routes plus the legacy `#docs`/`#settings` links. */
export function parseAppRoute(hash: string): AppRoute {
  const normalized = hash.replace(/^#\/?/, '').replace(/\/$/, '');
  const [head = '', detail] = normalized.split('/');
  if (head === 'docs') return { page: 'docs' };
  if (head === 'agent') return { page: 'agent' };
  if (head === 'browser' || head === 'knowledge') return { page: 'browser' };
  if (head === 'indexing') return { page: 'settings', settingsSection: 'indexing' };
  if (head === 'memory') return { page: 'settings', settingsSection: 'memory' };
  if (head === 'settings') {
    const section = SETTINGS_SECTIONS.has(detail as SettingsSection)
      ? detail as SettingsSection
      : 'general';
    return { page: 'settings', settingsSection: section };
  }
  if (head === 'chat') return { page: 'chat', chatId: safeDecode(detail) };
  return { page: 'chat' };
}

export function formatAppRoute(route: AppRoute): string {
  if (route.page === 'docs') return '#/docs';
  if (route.page === 'agent') return '#/agent';
  if (route.page === 'browser') return '#/knowledge';
  if (route.page === 'settings') return `#/settings/${route.settingsSection ?? 'general'}`;
  return route.chatId ? `#/chat/${encodeURIComponent(route.chatId)}` : '#/chat';
}
