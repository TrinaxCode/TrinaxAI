import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ChatMarkdown, { linkifyPlainUrls } from './ChatMarkdown';

describe('ChatMarkdown', () => {
  it('linkifies plain URLs without swallowing sentence punctuation', () => {
    expect(linkifyPlainUrls('Visita https://example.com/docs.')).toBe(
      'Visita [https://example.com/docs](https://example.com/docs).',
    );
  });

  it('renders safe external links and strips unsafe HTML', () => {
    render(<ChatMarkdown text={'Consulta www.example.com\n\n<script>alert("x")</script>'} isDark={false} />);

    const link = screen.getByRole('link', { name: 'www.example.com' });
    expect(link).toHaveAttribute('href', 'https://www.example.com');
    expect(link).toHaveAttribute('rel', 'noreferrer');
    expect(document.querySelector('script')).not.toBeInTheDocument();
  });

  it('loads KaTeX on demand and keeps its output after sanitization', async () => {
    const { container } = render(<ChatMarkdown text={'La ecuación es $x^2$.'} isDark />);
    await waitFor(
      () => expect(container.querySelector('.katex')).toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(container.querySelector('math')).not.toBeNull();
  });

  it('turns valid numbered web citations into source links', () => {
    render(<ChatMarkdown
      text="Dato verificado [1]. La cita [2] no tiene una fuente válida."
      isDark={false}
      sources={[{
        file: 'https://example.com/official',
        url: 'https://example.com/official',
        title: 'Official source',
        kind: 'web',
        project: '',
        snippet: 'Evidence',
        score: null,
      }]}
    />);

    expect(screen.getByRole('link', { name: '[1]' })).toHaveAttribute('href', 'https://example.com/official');
    expect(screen.queryByRole('link', { name: '[2]' })).not.toBeInTheDocument();
    expect(screen.getByText(/La cita \[2\]/)).toBeInTheDocument();
  });

  it('does not link citation-looking text inside code', () => {
    render(<ChatMarkdown
      text={'`value[1]`'}
      isDark={false}
      sources={[{
        file: 'https://example.com/source',
        url: 'https://example.com/source',
        project: '',
        snippet: '',
        score: null,
      }]}
    />);

    expect(screen.queryByRole('link', { name: '[1]' })).not.toBeInTheDocument();
    expect(screen.getByText('value[1]')).toBeInTheDocument();
  });
});
