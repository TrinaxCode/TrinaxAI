import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ChatSession } from '../lib/api';
import ChatSidebar from './ChatSidebar';

vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));

const session: ChatSession = {
  id: 'session-1',
  title: 'Research',
  messages: [{ role: 'user', content: 'Question' }],
  engine: 'ollama',
  createdAt: 1,
  updatedAt: 1,
};

function renderSidebar(overrides: Partial<React.ComponentProps<typeof ChatSidebar>> = {}) {
  const props: React.ComponentProps<typeof ChatSidebar> = {
    sessions: [session],
    activeId: null,
    isOpen: true,
    onToggle: vi.fn(),
    onSelect: vi.fn(),
    onDelete: vi.fn(),
    onCreate: vi.fn(),
    onCreateTemporary: vi.fn(),
    engine: 'ollama',
    onSettings: vi.fn(),
    folders: [],
    onCreateFolder: vi.fn(),
    onMoveToFolder: vi.fn(),
    onDeleteFolder: vi.fn(),
    ...overrides,
  };
  return { ...render(<ChatSidebar {...props} />), props };
}

describe('ChatSidebar session actions', () => {
  it('keeps session selection and destructive actions as sibling controls', () => {
    const { props } = renderSidebar();
    const select = screen.getByRole('button', { name: 'Research' });
    const deleteButton = screen.getByRole('button', { name: 'delete Research' });
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveAttribute('src', '/logo-for-ai-transparent.webp');

    expect(select.closest('[role="button"]')).toBeNull();
    expect(deleteButton.closest('[role="button"]')).toBeNull();

    fireEvent.click(select);
    expect(props.onSelect).toHaveBeenCalledWith(session.id);
    fireEvent.click(deleteButton);
    expect(screen.getByRole('dialog', { name: 'deleteChat' })).toBeInTheDocument();
  });
});
