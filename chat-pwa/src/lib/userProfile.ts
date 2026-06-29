import type { Lang } from '../i18n/translations';

const NAME_KEY = 'tc-user-name';
const NICKNAME_KEY = 'tc-user-nickname';
const AVATAR_KEY = 'tc-user-avatar';
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

export function getPreferredUserName(lang: Lang = detectedLang()): string {
  const nickname = cleanProfileName(readLocalStorage(NICKNAME_KEY));
  if (nickname) return nickname;
  const name = firstName(cleanProfileName(readLocalStorage(NAME_KEY)));
  if (name) return name;
  return lang === 'en' ? 'User' : 'Usuario';
}

export function getUserAvatar(): string {
  return readLocalStorage(AVATAR_KEY);
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
  const memory = getUserMemory();
  const memoryText = memory.length
    ? (lang === 'en'
      ? `\nPersistent local memory about the user:\n${memory.map((item) => `- ${item}`).join('\n')}`
      : `\nMemoria local persistente sobre el usuario:\n${memory.map((item) => `- ${item}`).join('\n')}`)
    : '';
  return lang === 'en'
    ? `The user prefers to be called "${name}". Use that name naturally when it is useful, but do not repeat greetings in follow-up messages.${memoryText}`
    : `El usuario prefiere que le llames "${name}". Usa ese nombre de forma natural cuando aporte claridad, pero no repitas saludos en mensajes de seguimiento.${memoryText}`;
}
