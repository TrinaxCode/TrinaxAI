/**
 * Keep the native pickers disjoint, especially on iOS Safari.
 * `image/*` without `capture` offers both Camera and Photo Library. The
 * document filter contains no image types, so that action opens Files.
 */
export const IMAGE_FILE_ACCEPT = 'image/*';

export const DOCUMENT_FILE_ACCEPT = [
  '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
  '.odt', '.ods', '.odp', '.rtf',
  '.txt', '.md', '.mdx', '.rst', '.csv', '.tsv',
  '.json', '.jsonl', '.xml', '.yaml', '.yml', '.toml',
  '.html', '.htm', '.css', '.js', '.jsx', '.ts', '.tsx',
  '.py', '.java', '.c', '.h', '.cpp', '.cs', '.go', '.rb',
  '.php', '.rs', '.swift', '.kt', '.sql', '.sh', '.zsh', '.ps1',
].join(',');
