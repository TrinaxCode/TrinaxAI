import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useReducedMotion } from 'framer-motion';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { translations, type Lang } from '../../i18n/translations';
import type { Translate } from '../chat/types';
import AgentEmptyState from './AgentEmptyState';
import { AGENT_SUGGESTIONS, AGENT_WELCOME_MESSAGES } from './agentWelcome';

vi.mock('framer-motion', async (importOriginal) => ({
  ...await importOriginal<typeof import('framer-motion')>(),
  useReducedMotion: vi.fn(() => false),
}));

const t: Translate = (key) => translations.es[key];
const advance = (milliseconds: number) => act(() => vi.advanceTimersByTime(milliseconds));
const labels = () => screen.getAllByRole('button').filter((button) => button.classList.contains('agent-suggestion')).map((button) => button.textContent);

describe('AgentEmptyState', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(useReducedMotion).mockReturnValue(false);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('rotates paired welcome copy every four seconds and three suggestions every fifteen seconds', () => {
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const original = labels();
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    advance(4_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentWelcomeTitle2'));
    expect(screen.getByText(t('agentWelcomeHint2'))).toBeInTheDocument();
    expect(labels()).toEqual(original);
    advance(11_000);
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(3, 6).map(t));
  });

  it.each<Lang>(['es', 'en'])('offers sixty unique working suggestions and forty complete messages in %s', (lang) => {
    const translate: Translate = (key) => translations[lang][key];
    const onSelect = vi.fn();
    render(<AgentEmptyState isDark={false} t={translate} paused={false} onSelect={onSelect} />);
    expect(AGENT_WELCOME_MESSAGES).toHaveLength(40);
    const seen = new Set<string>();
    for (let group = 0; group < 20; group++) {
      for (const label of AGENT_SUGGESTIONS.slice(group * 3, group * 3 + 3)) {
        expect(translate(label)).toBeTruthy();
        expect(translate(`${label}Prompt`)).toBeTruthy();
        fireEvent.click(screen.getByRole('button', { name: translate(label), exact: true }));
        expect(onSelect).toHaveBeenLastCalledWith(translate(`${label}Prompt`));
        seen.add(translate(label));
      }
      advance(15_000);
    }
    expect(seen.size).toBe(60);
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(0, 3).map(translate));
    for (const [title, hint] of AGENT_WELCOME_MESSAGES) {
      expect(translate(title)).toBeTruthy();
      expect(translate(hint)).toBeTruthy();
    }
  });

  it('cycles through every paired message before returning to the first', () => {
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    for (const [title, hint] of AGENT_WELCOME_MESSAGES) {
      expect(screen.getByRole('heading')).toHaveTextContent(t(title));
      expect(screen.getByText(t(hint))).toBeInTheDocument();
      advance(4_000);
    }
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
  });

  it('pauses while composing and resumes when composing ends', () => {
    const props = { isDark: true, t, onSelect: vi.fn() };
    const view = render(<AgentEmptyState {...props} paused />);
    advance(20_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(0, 3).map(t));
    view.rerender(<AgentEmptyState {...props} paused={false} />);
    advance(15_000);
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(3, 6).map(t));
  });

  it('keeps keyboard-focused suggestions stable, then resumes after focus leaves', () => {
    const { container } = render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const first = screen.getByRole('button', { name: t('quickChipFindBugs') });
    fireEvent.focus(first);
    advance(20_000);
    expect(first).toBeInTheDocument();
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    fireEvent.blur(first);
    advance(15_000);
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(3, 6).map(t));
    expect(container.querySelectorAll('button')).toHaveLength(3);
  });

  it('keeps rotating when the mouse stays over the welcome area', () => {
    const { container } = render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    fireEvent.pointerEnter(container.firstChild!, { pointerType: 'mouse' });
    advance(15_000);
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(3, 6).map(t));
  });

  it('does not advance while the tab is hidden', () => {
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    advance(20_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(0, 3).map(t));
  });

  it('rotates content without animation when reduced motion is requested', () => {
    vi.mocked(useReducedMotion).mockReturnValue(true);
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    advance(4_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentWelcomeTitle2'));
    expect(screen.getByRole('heading')).toBeVisible();
    advance(11_000);
    expect(labels()).toEqual(AGENT_SUGGESTIONS.slice(3, 6).map(t));
  });
});
