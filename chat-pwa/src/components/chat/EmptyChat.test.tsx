import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import EmptyChat from './EmptyChat';

describe('EmptyChat', () => {
  it('renders suggestions and delegates their action', async () => {
    const action = vi.fn();
    render(<EmptyChat isDark motd="Listo para ayudarte" rotation={0} chips={[{ label: 'Explicar código', icon: '💡', action, idx: 0 }]} />);

    expect(screen.getByText('Listo para ayudarte')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /explicar código/i }));
    expect(action).toHaveBeenCalledOnce();
  });

});
