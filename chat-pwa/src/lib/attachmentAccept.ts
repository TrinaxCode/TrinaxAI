/**
 * Keep the native pickers disjoint, especially on iOS Safari.
 * `image/*` without `capture` offers both Camera and Photo Library. The
 * document filter contains no image types, so that action opens Files.
 */
export const IMAGE_FILE_ACCEPT = 'image/*';
export const MAX_ATTACHMENTS_PER_TYPE = 3;

export function appendAttachmentSelection<T>(current: T[], selected: T[], limit = MAX_ATTACHMENTS_PER_TYPE): T[] {
  return [...current, ...selected].slice(0, Math.max(0, limit));
}

export function filesFromDataTransfer(data: DataTransfer | null): File[] {
  if (!data) return [];
  const files = Array.from(data.files);
  if (files.length) return files;
  return Array.from(data.items)
    .filter((item) => item.kind === 'file')
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file));
}

export function imageFilesFrom(files: File[]): File[] {
  return files.filter((file) => file.type.toLowerCase().startsWith('image/'));
}

export const DOCUMENT_FILE_ACCEPT = [
  '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
  '.odt', '.ods', '.odp', '.rtf',
  '.txt', '.md', '.mdx', '.rst', '.csv', '.tsv',
  '.json', '.jsonl', '.xml', '.yaml', '.yml', '.toml',
  '.html', '.htm', '.css', '.js', '.jsx', '.ts', '.tsx',
  '.py', '.java', '.c', '.h', '.cpp', '.cs', '.go', '.rb',
  '.php', '.rs', '.swift', '.kt', '.sql', '.sh', '.zsh', '.ps1',
].join(',');
