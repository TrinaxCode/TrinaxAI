/** Generate a short title from the first user message without loading the API client. */
export function generateTitle(message: string): string {
  const cleaned = message.replace(/\n/g, ' ').trim();
  return cleaned.length > 50 ? `${cleaned.slice(0, 47)}…` : cleaned;
}

/** Small local identifier for chat and folder records. */
export function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
}
