const isDev = import.meta.env.DEV;

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

function sameOrigin(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

export const APP_CONFIG = {
  repoUrl: import.meta.env.VITE_TRINAXAI_REPO_URL || 'https://github.com/TrinaxCode/TrinaxAI',
  docsUrl: import.meta.env.VITE_TRINAXAI_DOCS_URL || 'https://github.com/TrinaxCode/TrinaxAI#readme',
  defaultIndexDir: import.meta.env.VITE_TRINAXAI_INDEX_DIR || '',
  ragBase: isDev
    ? sameOrigin(import.meta.env.VITE_TRINAXAI_DEV_RAG_BASE || '/api/rag')
    : trimTrailingSlash(import.meta.env.VITE_TRINAXAI_RAG_BASE || `${window.location.origin}/api/rag`),
  ollamaBase: isDev
    ? sameOrigin(import.meta.env.VITE_TRINAXAI_DEV_OLLAMA_BASE || '/api/ollama')
    : trimTrailingSlash(import.meta.env.VITE_TRINAXAI_OLLAMA_BASE || `${window.location.origin}/api/ollama`),
};
