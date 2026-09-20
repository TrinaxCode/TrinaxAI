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
    expect(picker.closest('main')).toBeNull();
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
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveClass('h-10', 'w-10');
    expect(await screen.findByText(/Your private assistant/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Repository reference' })).toHaveAttribute(
      'href',
      'https://github.com/TrinaxCode/TrinaxAI/blob/main/README.md#quick-start',
    );
    await user.selectOptions(screen.getByRole('combobox', { name: 'Select section' }), 'indexing');
    expect(screen.getAllByRole('link', { name: /Open on GitHub/ })[0]).toHaveAttribute('href', expect.stringContaining('/docs/ARCHITECTURE.md'));
    expect(screen.queryByText('Image coming soon')).not.toBeInTheDocument();
  });

  it('exposes deep links for every section and moves focus into the opened section', async () => {
    const user = userEvent.setup();
    const onSectionChange = vi.fn();
    render(<Docs onBack={vi.fn()} onSectionChange={onSectionChange} />);

    const introLink = screen.getByRole('link', { name: 'Introduction' });
    const securityLink = screen.getByRole('link', { name: 'Security' });

    expect(introLink).toHaveAttribute('href', '#/docs/intro');
    expect(introLink).toHaveAttribute('aria-current', 'page');
    expect(securityLink).toHaveAttribute('href', '#/docs/security');
    expect(securityLink).not.toHaveAttribute('aria-current');

    await user.click(securityLink);

    expect(onSectionChange).toHaveBeenCalledWith('security');
    expect(securityLink).toHaveAttribute('aria-current', 'page');
    expect(introLink).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('heading', { level: 1, name: 'Security' })).toHaveFocus();
  });

  it('navigates to the previous and next sections', async () => {
    const user = userEvent.setup();
    render(<Docs onBack={vi.fn()} />);

    expect(screen.queryByRole('link', { name: /^Previous:/ })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Next: About' })).toHaveAttribute('href', '#/docs/about');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Select section' }), 'community');

    expect(screen.getByRole('link', { name: 'Previous: Contributing' })).toHaveAttribute('href', '#/docs/contributing');
    expect(screen.queryByRole('link', { name: /^Next:/ })).not.toBeInTheDocument();
  });

  it('shows a loading placeholder until the references resolve', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<Docs onBack={vi.fn()} />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading documentation…');
  });

  it('offers a repository fallback when a reference is missing from the build', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, text: async () => '' })));
    render(<Docs onBack={vi.fn()} />);

    expect(await screen.findByText('This reference is not bundled in this build of the PWA.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Read it on GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/TrinaxCode/TrinaxAI/blob/main/README.md',
    );
  });
});
