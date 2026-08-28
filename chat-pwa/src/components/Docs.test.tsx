import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Docs from './Docs';

vi.mock('../i18n/I18nContext', () => ({
  useI18n: () => ({ lang: 'en', t: (key: string) => key }),
}));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ isDark: false }),
}));

describe('PWA documentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens every local section through the mobile navigation and supports Back', async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    render(<Docs onBack={onBack} />);

    const picker = screen.getByRole('combobox', { name: 'Select section' });
    const sectionIds = Array.from(picker.querySelectorAll('option')).map((option) => option.value);

    expect(sectionIds).toHaveLength(14);
    for (const sectionId of sectionIds) {
      await user.selectOptions(picker, sectionId);
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    }

    await user.click(screen.getByRole('button', { name: 'docsBack' }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('links to canonical architecture docs without a placeholder image', async () => {
    const user = userEvent.setup();
    render(<Docs onBack={vi.fn()} />);

    expect(screen.getByText('Canonical documentation')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveAttribute('src', '/logo-for-ai-transparent.webp');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Select section' }), 'indexing');
    expect(screen.getByRole('link', { name: /Flow and storage/ })).toHaveAttribute('href', expect.stringContaining('/docs/ARCHITECTURE.md'));
    expect(screen.queryByText('Image coming soon')).not.toBeInTheDocument();
  });
});
