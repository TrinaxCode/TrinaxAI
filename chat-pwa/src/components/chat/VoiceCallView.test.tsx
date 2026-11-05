import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { I18nProvider } from '../../i18n/I18nContext';
import VoiceCallView from './VoiceCallView';

describe('VoiceCallView palette', () => {
  it('uses TrinaxAI blue for the call surface and red only for ending the call', () => {
    const { container } = render(
      <I18nProvider>
        <VoiceCallView isDark listening={false} speaking={true} thinking={false} onEnd={() => undefined} />
      </I18nProvider>,
    );

    expect(container.innerHTML).not.toContain('rose');
    expect(container.innerHTML).toContain('via-[#006bbd]');
    expect(container.innerHTML).toContain('from-[#4ea3e0]');

    const endCall = screen.getByRole('button');
    expect(endCall).toHaveFocus();
    expect(endCall).toHaveClass('bg-red-600');
    expect(endCall).toHaveClass('hover:bg-red-700');
    expect(screen.getByRole('heading', { level: 1, name: 'Call mode' })).toBeInTheDocument();
  });

  it('captions what is being heard while listening and the reply while it is spoken', () => {
    const { rerender, container } = render(
      <I18nProvider>
        <VoiceCallView isDark listening speaking={false} thinking={false} heard="hola, cómo estás" reply="ignorado" onEnd={() => undefined} />
      </I18nProvider>,
    );
    const caption = () => container.querySelector('.voice-call-caption')?.textContent;
    expect(caption()).toBe('hola, cómo estás');

    rerender(
      <I18nProvider>
        <VoiceCallView isDark listening={false} speaking thinking={false} heard="" reply="Estoy muy bien, gracias." onEnd={() => undefined} />
      </I18nProvider>,
    );
    expect(caption()).toBe('Estoy muy bien, gracias.');
  });

  it('keeps only the newest words of a long reply', () => {
    const reply = `${'palabra '.repeat(80)}final`;
    const { container } = render(
      <I18nProvider>
        <VoiceCallView isDark listening={false} speaking thinking={false} reply={reply} onEnd={() => undefined} />
      </I18nProvider>,
    );
    const text = container.querySelector('.voice-call-caption')?.textContent ?? '';
    expect(text.startsWith('…')).toBe(true);
    expect(text.endsWith('final')).toBe(true);
    expect(text.length).toBeLessThanOrEqual(201);
  });
});
