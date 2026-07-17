import { defaultSchema } from 'rehype-sanitize';
import type { Source } from '../../lib/api';

const PLAIN_URL_RE = /(^|[\s(])((?:https?:\/\/|www\.)[^\s<>()]+)(?=[\s)]|$)/g;
const TRAILING_PUNCT_RE = /[.,;:!?'"»]+$/;

export function linkifyPlainUrls(text: string): string {
  return text
    .split(/(```[\s\S]*?```|`[^`]*`)/g)
    .map((part) => {
      if (part.startsWith('`')) return part;
      return part.replace(PLAIN_URL_RE, (match, prefix: string, url: string, offset: number, source: string) => {
        if (prefix === '(' && source[offset - 1] === ']') return match;
        let cleanUrl = url;
        let trailing = '';
        const punctMatch = cleanUrl.match(TRAILING_PUNCT_RE);
        if (punctMatch) {
          trailing = punctMatch[0];
          cleanUrl = cleanUrl.slice(0, -trailing.length);
        }
        const href = cleanUrl.startsWith('www.') ? `https://${cleanUrl}` : cleanUrl;
        return `${prefix}[${cleanUrl}](${href})${trailing}`;
      });
    })
    .join('');
}

function safeCitationUrl(source?: Source): string | null {
  if (!source?.url) return null;
  try {
    const parsed = new URL(source.url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null;
  } catch {
    return null;
  }
}

export function citationLinksPlugin(sources: Source[]) {
  return () => (tree: any) => {
    const walk = (node: any, parent?: any) => {
      if (!node || !Array.isArray(node.children)) return;
      node.children = node.children.flatMap((child: any) => {
        if (child?.type !== 'text' || parent?.type === 'link' || node.type === 'link') {
          walk(child, node);
          return [child];
        }
        const parts = [];
        const pattern = /\[(\d+)\]/g;
        let cursor = 0;
        let match: RegExpExecArray | null;
        while ((match = pattern.exec(child.value)) !== null) {
          const sourceIndex = Number(match[1]) - 1;
          const url = safeCitationUrl(sources[sourceIndex]);
          if (!url) continue;
          if (match.index > cursor) parts.push({ type: 'text', value: child.value.slice(cursor, match.index) });
          parts.push({
            type: 'link',
            url,
            title: sources[sourceIndex]?.title || `Source ${sourceIndex + 1}`,
            children: [{ type: 'text', value: match[0] }],
          });
          cursor = match.index + match[0].length;
        }
        if (cursor === 0) return [child];
        if (cursor < child.value.length) parts.push({ type: 'text', value: child.value.slice(cursor) });
        return parts;
      });
    };
    walk(tree);
  };
}

const MATHML_TAGS = [
  'math', 'semantics', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'msubsup',
  'mfrac', 'msqrt', 'mroot', 'mtable', 'mtr', 'mtd', 'mspace', 'mtext',
  'annotation',
];

export const katexSanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), ...MATHML_TAGS],
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span ?? []), 'className', 'style', 'ariaHidden'],
    div: [...(defaultSchema.attributes?.div ?? []), 'className', 'style', 'ariaHidden'],
    '*': [...(defaultSchema.attributes?.['*'] ?? []), 'className', 'style', 'ariaHidden'],
    math: ['xmlns', 'display'],
    annotation: ['encoding'],
    mspace: ['width', 'height', 'depth', 'linebreak'],
    mo: ['stretchy', 'fence', 'separator', 'lspace', 'rspace'],
    mfrac: ['linethickness'],
  },
};

export function containsMath(text: string): boolean {
  return /(^|[^\\])\$\$?[\s\S]*?\$\$?|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]/m.test(text);
}
