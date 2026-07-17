import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { expectNoA11yViolations } from '../test/a11y';
import Sources from './Sources';

vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));

describe('Sources accessibility', () => {
  it('exposes disclosure state and a keyboard-operable local path', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    render(<Sources sources={[{
      file: 'docs/guide.md',
      project: 'TrinaxAI',
      snippet: 'Grounded evidence',
      score: 0.9,
    }]} />);

    const disclosure = screen.getByRole('button', { name: /1 source/i });
    expect(disclosure).toHaveAttribute('aria-expanded', 'false');
    await user.click(disclosure);
    expect(disclosure).toHaveAttribute('aria-expanded', 'true');

    const pathButton = screen.getByRole('button', { name: 'copy: docs/guide.md' });
    pathButton.focus();
    await user.keyboard('{Enter}');
    expect(writeText).toHaveBeenCalledWith('docs/guide.md');
  });

  it('has no automatically detectable expanded-source violations', async () => {
    const user = userEvent.setup();
    render(<Sources sources={[{
      file: 'docs/guide.md',
      project: 'TrinaxAI',
      snippet: 'Grounded evidence',
      score: 0.9,
    }]} />);
    await user.click(screen.getByRole('button', { name: /1 source/i }));

    await expectNoA11yViolations(document.body);
  });
});
