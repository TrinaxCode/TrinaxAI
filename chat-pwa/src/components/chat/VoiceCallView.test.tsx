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
    expect(endCall).toHaveClass('bg-red-500');
    expect(endCall).toHaveClass('hover:bg-red-600');
  });
});
