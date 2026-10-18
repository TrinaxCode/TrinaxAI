import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
  it('focuses the folder name and enables creation only for a nonempty name', async () => {
    const user = userEvent.setup();
    const { props } = renderSidebar();
    await user.click(screen.getByRole('button', { name: 'createFolder' }));
    const name = screen.getByRole('textbox', { name: 'folderName' });
    const create = screen.getByRole('dialog').querySelector<HTMLButtonElement>('button:last-child')!;
    await waitFor(() => expect(name).toHaveFocus());
    expect(create).toBeDisabled();
    await user.type(name, '  Ideas  ');
    expect(create).toBeEnabled();
    await user.click(create);
    expect(props.onCreateFolder).toHaveBeenCalledWith('Ideas');
  });

  it('keeps session selection and destructive actions as sibling controls', () => {
    const { props } = renderSidebar();
    const select = screen.getByRole('button', { name: 'Research' });
    fireEvent.click(screen.getByRole('button', { name: 'chatOptions: Research' }));
    const deleteButton = screen.getByRole('button', { name: 'deleteChat' });
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveAttribute('src', '/logo-for-ai-transparent.webp');

    expect(select.closest('[role="button"]')).toBeNull();
    expect(deleteButton.closest('[role="button"]')).toBeNull();

    fireEvent.click(select);
    expect(props.onSelect).toHaveBeenCalledWith(session.id);
    fireEvent.click(deleteButton);
    expect(screen.getByRole('dialog', { name: 'deleteChat' })).toBeInTheDocument();
  });
});
