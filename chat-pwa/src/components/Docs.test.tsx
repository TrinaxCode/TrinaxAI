import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      text: async () => '> Your private assistant for working with your files on your own computer.\n\n[Repository reference](../README.md#quick-start)',
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens every local section through the mobile navigation and supports Back', async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    render(<Docs onBack={onBack} />);

    const picker = screen.getByRole('combobox', { name: 'Select section' });
    const sectionIds = Array.from(picker.querySelectorAll('option')).map((option) => option.value);

    expect(sectionIds).toHaveLength(15);
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

    expect(screen.getByText('Integrated guide')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveAttribute('src', '/logo-for-ai-transparent.webp');
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveClass('h-14', 'w-14');
    expect(await screen.findByText(/Your private assistant/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Repository reference' })).toHaveAttribute(
      'href',
      'https://github.com/TrinaxCode/TrinaxAI/blob/main/README.md#quick-start',
    );
    await user.selectOptions(screen.getByRole('combobox', { name: 'Select section' }), 'indexing');
    expect(screen.getAllByRole('link', { name: /Open reference/ })[0]).toHaveAttribute('href', expect.stringContaining('/docs/ARCHITECTURE.md'));
    expect(screen.queryByText('Image coming soon')).not.toBeInTheDocument();
  });
});
