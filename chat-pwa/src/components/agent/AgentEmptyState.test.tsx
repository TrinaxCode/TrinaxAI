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
  // Exit animations never complete under fake timers, so swap content immediately.
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const t: Translate = (key) => translations.es[key];
const advance = (milliseconds: number) => act(() => vi.advanceTimersByTime(milliseconds));
const labels = () => screen.getAllByRole('button').filter((button) => button.classList.contains('chip-elegant')).map((button) => button.textContent ?? '');
const suggestionLabels = new Set(AGENT_SUGGESTIONS.map((key) => t(key)));

describe('AgentEmptyState', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(useReducedMotion).mockReturnValue(false);
    // Random 0 makes the welcome copy start at the first message.
    vi.spyOn(Math, 'random').mockReturnValue(0);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('rotates paired welcome copy every four seconds and a fresh set of three suggestions every fifteen seconds', () => {
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const original = labels();
    expect(original).toHaveLength(3);
    expect(new Set(original).size).toBe(3);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    advance(4_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentWelcomeTitle2'));
    expect(screen.getByText(t('agentWelcomeHint2'))).toBeInTheDocument();
    expect(labels()).toEqual(original);
    advance(11_000);
    const next = labels();
    expect(next).toHaveLength(3);
    expect(next.filter((label) => original.includes(label))).toEqual([]);
    expect(next.every((label) => suggestionLabels.has(label))).toBe(true);
  });

  it.each<Lang>(['es', 'en'])('offers sixty unique working suggestions and forty complete messages in %s', (lang) => {
    const translate: Translate = (key) => translations[lang][key];
    const onSelect = vi.fn();
    render(<AgentEmptyState isDark={false} t={translate} paused={false} onSelect={onSelect} />);
    expect(AGENT_WELCOME_MESSAGES).toHaveLength(40);
    expect(AGENT_SUGGESTIONS).toHaveLength(60);
    expect(new Set(AGENT_SUGGESTIONS).size).toBe(60);
    const seen = new Set<string>();
    for (let group = 0; group < 20; group++) {
      for (const button of screen.getAllByRole('button').filter((item) => item.classList.contains('chip-elegant'))) {
        const key = AGENT_SUGGESTIONS.find((suggestion) => translate(suggestion) === button.textContent);
        expect(key).toBeDefined();
        expect(translate(`${key!}Prompt`)).toBeTruthy();
        fireEvent.click(button);
        expect(onSelect).toHaveBeenLastCalledWith(translate(`${key!}Prompt`));
        seen.add(key!);
      }
      advance(15_000);
    }
    expect(seen.size).toBe(60);
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

  it('reshuffles the welcome copy when a new session starts', () => {
    const props = { isDark: true, t, paused: false, onSelect: vi.fn() };
    const view = render(<AgentEmptyState {...props} resetKey={0} />);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    vi.mocked(Math.random).mockReturnValue(0.5);
    view.rerender(<AgentEmptyState {...props} resetKey={1} />);
    const [title] = AGENT_WELCOME_MESSAGES[Math.floor(0.5 * AGENT_WELCOME_MESSAGES.length)];
    expect(screen.getByRole('heading')).toHaveTextContent(t(title));
  });

  it('pauses while composing and resumes when composing ends', () => {
    const props = { isDark: true, t, onSelect: vi.fn() };
    const view = render(<AgentEmptyState {...props} paused />);
    const original = labels();
    advance(20_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    expect(labels()).toEqual(original);
    view.rerender(<AgentEmptyState {...props} paused={false} />);
    advance(15_000);
    expect(labels()).not.toEqual(original);
  });

  it('keeps keyboard-focused suggestions stable, then resumes after focus leaves', () => {
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const original = labels();
    const first = screen.getAllByRole('button')[0];
    fireEvent.focus(first);
    advance(20_000);
    expect(first).toBeInTheDocument();
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    expect(labels()).toEqual(original);
    fireEvent.blur(first);
    advance(15_000);
    expect(labels()).not.toEqual(original);
    expect(screen.getAllByRole('button')).toHaveLength(3);
  });

  it('keeps rotating when the mouse stays over the welcome area', () => {
    const { container } = render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const original = labels();
    fireEvent.pointerEnter(container.firstChild!, { pointerType: 'mouse' });
    advance(15_000);
    expect(labels()).not.toEqual(original);
  });

  it('does not advance while the tab is hidden', () => {
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const original = labels();
    advance(20_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentEmptyTitle'));
    expect(labels()).toEqual(original);
  });

  it('rotates content without animation when reduced motion is requested', () => {
    vi.mocked(useReducedMotion).mockReturnValue(true);
    render(<AgentEmptyState isDark t={t} paused={false} onSelect={vi.fn()} />);
    const original = labels();
    advance(4_000);
    expect(screen.getByRole('heading')).toHaveTextContent(t('agentWelcomeTitle2'));
    expect(screen.getByRole('heading')).toBeVisible();
    advance(11_000);
    expect(labels()).not.toEqual(original);
  });
});
