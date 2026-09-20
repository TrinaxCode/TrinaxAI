import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { ChatFolder, ChatSession } from '../lib/api';
import ChatSidebar from './ChatSidebar';

const theme = vi.hoisted(() => ({ isDark: false }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => theme }));

const makeSession = (id: string, title: string, folderId?: string): ChatSession => ({
  id,
  title,
  messages: [{ role: 'user', content: `${title} question\nwith a second line` }],
  engine: 'ollama',
  createdAt: 1,
  updatedAt: 1,
  folderId,
});

const folder: ChatFolder = { id: 'work', name: 'Work', createdAt: 1, updatedAt: 1 };

function renderSidebar(overrides: Partial<React.ComponentProps<typeof ChatSidebar>> = {}) {
  const props: React.ComponentProps<typeof ChatSidebar> = {
    sessions: [makeSession('general', 'General chat'), makeSession('work-chat', 'Work chat', 'work')],
    activeId: 'work-chat',
    isOpen: true,
    onToggle: vi.fn(),
    onSelect: vi.fn(),
    onDelete: vi.fn(),
    onCreate: vi.fn(),
    onCreateTemporary: vi.fn(),
    engine: 'ollama',
    onSettings: vi.fn(),
    folders: [folder],
    onCreateFolder: vi.fn(),
    onMoveToFolder: vi.fn(),
    onDeleteFolder: vi.fn(),
    ...overrides,
  };
  return { ...render(<ChatSidebar {...props} />), props };
}

describe('ChatSidebar release paths', () => {
  it('covers folder filters, session moves, search, collapse and header actions', async () => {
    const user = userEvent.setup();
    const { props } = renderSidebar({ onBrowser: vi.fn() });

    await user.click(screen.getByRole('button', { name: 'knowledgeBrowser' }));
    await user.click(screen.getByRole('button', { name: 'settings' }));
    await user.click(screen.getByRole('button', { name: 'closeMenu' }));
    expect(props.onBrowser).toHaveBeenCalledOnce();
    expect(props.onSettings).toHaveBeenCalledOnce();
    expect(props.onToggle).toHaveBeenCalledOnce();

    const workFilter = screen.getByTitle('Work');
    await user.click(workFilter);
    const workGroup = screen.getAllByRole('button', { name: 'Work1' })[1];
    await user.click(workGroup);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Work chat' })).not.toBeInTheDocument());
    await user.click(workGroup);

    const row = screen.getByRole('button', { name: 'Work chat' }).closest('[data-session-row]') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'moveChatToFolder' }));
    await user.click(screen.getByRole('button', { name: 'generalFolder' }));
    expect(props.onMoveToFolder).toHaveBeenCalledWith('work-chat', undefined);
    await user.click(within(row).getByRole('button', { name: 'moveChatToFolder' }));
    await user.click(screen.getByRole('button', { name: 'Work', exact: true }));
    expect(props.onMoveToFolder).toHaveBeenCalledWith('work-chat', 'work');

    const search = screen.getByRole('textbox', { name: 'searchChats' });
    await user.type(search, 'missing');
    expect(screen.getByText('noChatResults')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'clearSearch' }));
    expect(search).toHaveValue('');
  });

  it('creates and deletes folders and sessions, including the empty-name guard', async () => {
    const user = userEvent.setup();
    const { props } = renderSidebar();

    await user.click(screen.getByRole('button', { name: 'createFolder' }));
    const createDialog = screen.getByRole('dialog', { name: 'createFolder' });
    await user.click(within(createDialog).getByRole('button', { name: 'createFolder' }));
    expect(props.onCreateFolder).not.toHaveBeenCalled();
    await user.type(within(createDialog).getByRole('textbox', { name: 'folderName' }), '  Release  ');
    await user.keyboard('{Enter}');
    expect(props.onCreateFolder).toHaveBeenCalledWith('Release');

    await user.click(screen.getByRole('button', { name: 'delete Work' }));
    const folderDialog = screen.getByRole('dialog', { name: 'deleteFolder' });
    await user.click(within(folderDialog).getByRole('button', { name: 'delete' }));
    expect(props.onDeleteFolder).toHaveBeenCalledWith('work');

    await user.click(screen.getByRole('button', { name: 'delete General chat' }));
    const chatDialog = screen.getByRole('dialog', { name: 'deleteChat' });
    await user.click(within(chatDialog).getByRole('button', { name: 'delete' }));
    expect(props.onDelete).toHaveBeenCalledWith('general');

    await user.click(screen.getByRole('button', { name: 'newChat' }));
    await user.click(screen.getByRole('button', { name: 'temporaryChat' }));
    expect(props.onCreate).toHaveBeenCalledWith('ollama');
    expect(props.onCreateTemporary).toHaveBeenCalledWith('ollama');
  });

  it('handles mobile swipe, closed state, and dark visual branches', () => {
    const onToggle = vi.fn();
    theme.isDark = true;
    const { container, rerender } = renderSidebar({ onToggle });
    const overlay = container.querySelector('.sidebar-backdrop') as HTMLElement;
    fireEvent.touchStart(overlay, { touches: [{ clientX: 100, clientY: 5 }] });
    fireEvent.touchEnd(overlay, { changedTouches: [{ clientX: 10, clientY: 8 }] });
    expect(onToggle).toHaveBeenCalledOnce();
    fireEvent.touchStart(overlay, { touches: [{ clientX: 10, clientY: 5 }] });
    fireEvent.touchEnd(overlay, { changedTouches: [{ clientX: 80, clientY: 100 }] });
    expect(onToggle).toHaveBeenCalledOnce();

    rerender(<ChatSidebar {...({
      sessions: [], activeId: null, isOpen: false, onToggle, onSelect: vi.fn(), onDelete: vi.fn(),
      onCreate: vi.fn(), onCreateTemporary: vi.fn(), engine: 'ollama', onSettings: vi.fn(),
      folders: [], onCreateFolder: vi.fn(), onMoveToFolder: vi.fn(), onDeleteFolder: vi.fn(),
    } as React.ComponentProps<typeof ChatSidebar>)} />);
    expect(screen.getByRole('complementary', { hidden: true })).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByText('noChats')).toBeInTheDocument();
    theme.isDark = false;
  });
});
