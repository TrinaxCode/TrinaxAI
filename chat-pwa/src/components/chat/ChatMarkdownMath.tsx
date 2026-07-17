import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import type { Source } from '../../lib/api';
import { citationLinksPlugin, katexSanitizeSchema, linkifyPlainUrls } from './markdownSupport';
import 'katex/dist/katex.min.css';

interface Props {
  text: string;
  isDark: boolean;
  sources: Source[];
}

export default function ChatMarkdownMath({ text, isDark, sources }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath, citationLinksPlugin(sources)]}
      rehypePlugins={[rehypeKatex, [rehypeSanitize, katexSanitizeSchema]]}
      components={{
        a: ({ children, href }) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className={`underline decoration-1 underline-offset-2 ${isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
          >
            {children}
          </a>
        ),
      }}
    >
      {linkifyPlainUrls(text)}
    </ReactMarkdown>
  );
}
