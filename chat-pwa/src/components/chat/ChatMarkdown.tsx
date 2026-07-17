import { lazy, memo, Suspense } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import type { Source } from '../../lib/api';
import { citationLinksPlugin, containsMath, linkifyPlainUrls } from './markdownSupport';

const ChatMarkdownMath = lazy(() => import('./ChatMarkdownMath'));
export { linkifyPlainUrls } from './markdownSupport';

interface ChatMarkdownProps {
  text: string;
  isDark: boolean;
  sources?: Source[];
}

function ChatMarkdown({ text, isDark, sources = [] }: ChatMarkdownProps) {
  const link = ({ children, href }: { children?: React.ReactNode; href?: string }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`underline decoration-1 underline-offset-2 ${isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
    >
      {children}
    </a>
  );

  return (
    <div className={`chat-markdown prose prose-sm min-w-0 max-w-full break-words [overflow-wrap:anywhere] ${isDark ? 'prose-invert' : ''}`}>
      {containsMath(text) ? (
        <Suspense fallback={<p className="chat-plain-text whitespace-pre-wrap">{text}</p>}>
          <ChatMarkdownMath text={text} isDark={isDark} sources={sources} />
        </Suspense>
      ) : (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, citationLinksPlugin(sources)]}
          rehypePlugins={[rehypeSanitize]}
          components={{ a: link }}
        >
          {linkifyPlainUrls(text)}
        </ReactMarkdown>
      )}
    </div>
  );
}

export default memo(ChatMarkdown);
