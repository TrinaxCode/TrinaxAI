import type { Lang } from '../i18n/translations';

const NAME_KEY = 'tc-user-name';
export const NICKNAME_KEY = 'tc-user-nickname';
const LANG_KEY = 'tc-lang';
const MEMORY_KEY = 'tc-user-memory';
const RESERVED_PROFILE_NAMES = new Set(['trinaxcode', 'trinaxai']);

function readLocalStorage(key: string): string {
  try {
    return localStorage.getItem(key)?.trim() ?? '';
  } catch {
    return '';
  }
}

function detectedLang(): Lang {
  const stored = readLocalStorage(LANG_KEY);
  if (stored === 'en' || stored === 'es') return stored;
  try {
    return navigator.language?.slice(0, 2) === 'en' ? 'en' : 'es';
  } catch {
    return 'es';
  }
}

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? '';
}

function cleanProfileName(value: string): string {
  const name = value.trim();
  return RESERVED_PROFILE_NAMES.has(name.toLowerCase()) ? '' : name;
}

export function isValidProfileName(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.length > 0 && !RESERVED_PROFILE_NAMES.has(trimmed.toLowerCase());
}

export function getPreferredUserName(lang: Lang = detectedLang()): string {
  const nickname = cleanProfileName(readLocalStorage(NICKNAME_KEY));
  if (nickname) return nickname;
  const name = firstName(cleanProfileName(readLocalStorage(NAME_KEY)));
  if (name) return name;
  return lang === 'en' ? 'User' : 'Usuario';
}

export function getUserMemory(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(MEMORY_KEY) || '[]');
    return Array.isArray(parsed)
      ? parsed.filter((item) => typeof item === 'string' && item.trim()).slice(-30)
      : [];
  } catch {
    return [];
  }
}

export function rememberFromMessage(text: string): boolean {
  const match = text.match(/\b(?:recuerda que|remember that)\s+(.{4,400})/i);
  const value = match?.[1]?.trim().replace(/\s+/g, ' ');
  if (!value) return false;
  const memory = getUserMemory().filter((item) => item.toLowerCase() !== value.toLowerCase());
  memory.push(value);
  localStorage.setItem(MEMORY_KEY, JSON.stringify(memory.slice(-30)));
  return true;
}

export function getUserSystemInstruction(lang: Lang = detectedLang()): string {
  const name = getPreferredUserName(lang);
  return lang === 'en'
    ? `Preferred user name: "${name}".`
    : `Nombre preferido del usuario: "${name}".`;
}
