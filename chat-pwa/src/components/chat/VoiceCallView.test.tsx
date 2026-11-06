import { render, screen, waitFor } from '@testing-library/react';
import { AnimatePresence } from 'framer-motion';
import { describe, expect, it } from 'vitest';

import { I18nProvider } from '../../i18n/I18nContext';
import VoiceCallView from './VoiceCallView';

describe('VoiceCallView palette', () => {
  it.each([
    [true, 'bg-black'],
    [false, 'bg-white'],
  ])('draws the call disc for isDark=%s with %s and red only for ending the call', (isDark, disc) => {
    const { container } = render(
      <I18nProvider>
        <VoiceCallView isDark={isDark} listening={false} speaking={true} thinking={false} onEnd={() => undefined} />
      </I18nProvider>,
    );

    expect(container.innerHTML).not.toContain('rose');
    expect(container.querySelector('.voice-call-core')).toHaveClass(disc);
    // The mark keeps its own colours, so it is never tinted white.
    expect(container.querySelector('.vc-mark')).not.toBeNull();

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

  it.each([
    ['listening', { listening: true, speaking: false, thinking: false }, 'mic'],
    ['idle', { listening: false, speaking: false, thinking: false }, 'mic'],
    ['thinking', { listening: false, speaking: false, thinking: true }, 'mark'],
    ['speaking', { listening: false, speaking: true, thinking: false }, 'mark'],
  ])('shows the %s emblem', (state, flags, emblem) => {
    const { container } = render(
      <I18nProvider>
        <VoiceCallView isDark {...flags} onEnd={() => undefined} />
      </I18nProvider>,
    );
    const orb = container.querySelector('.voice-call-orb');
    expect(orb).toHaveAttribute('data-call-state', state);
    expect(orb).toHaveAttribute('data-emblem', emblem);
    // The radial equalizer only exists while TrinaxAI is the one speaking.
    expect(container.querySelectorAll('.vc-bar')).toHaveLength(state === 'speaking' ? 40 : 0);
  });

  it('plays a hang-up animation before the surface is released', async () => {
    const Harness = ({ open }: { open: boolean }) => (
      <I18nProvider>
        <AnimatePresence>
          {open && <VoiceCallView isDark listening speaking={false} thinking={false} onEnd={() => undefined} />}
        </AnimatePresence>
      </I18nProvider>
    );
    const { rerender, container } = render(<Harness open />);
    expect(container.querySelector('[data-call-state="listening"]')).not.toBeNull();

    rerender(<Harness open={false} />);
    expect(container.querySelector('[data-call-state="ending"]')).not.toBeNull();
    expect(screen.getByText('Call ended')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();

    await waitFor(() => expect(container.querySelector('[data-call-state]')).toBeNull(), { timeout: 3000 });
  });
});
