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

  it('keeps the logo styling and changes only the avatar background by theme', () => {
    const props = { motd: '', rotation: 0, chips: [] };
    const { rerender } = render(<EmptyChat {...props} isDark />);
    const darkLogo = screen.getByRole('img', { name: 'TrinaxAI' });

    expect(darkLogo).toHaveClass('object-contain');
    expect(darkLogo.parentElement).toHaveClass('bg-black');

    rerender(<EmptyChat {...props} isDark={false} />);
    const lightLogo = screen.getByRole('img', { name: 'TrinaxAI' });
    expect(lightLogo).not.toHaveClass('animate-glow');
    expect(lightLogo.parentElement).toHaveClass(
      'bg-white',
      'shadow-[0_0_14px_1px_rgba(15,23,42,0.14)]',
    );
  });

});
