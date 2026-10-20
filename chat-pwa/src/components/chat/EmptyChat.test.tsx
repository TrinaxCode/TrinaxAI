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

  it('restores the original floating logo in both themes', () => {
    const props = { motd: '', rotation: 0, chips: [] };
    const { rerender } = render(<EmptyChat {...props} isDark />);
    const darkLogo = screen.getByRole('img', { name: 'TrinaxAI' });

    expect(darkLogo).toHaveClass('object-contain');
    expect(darkLogo).toHaveClass('animate-glow');
    expect(darkLogo.closest('.empty-chat-visual')).toHaveClass('animate-float');
    expect(darkLogo.parentElement).toHaveClass('bg-black', 'h-20', 'w-20', 'md:h-24', 'md:w-24');

    rerender(<EmptyChat {...props} isDark={false} />);
    const lightLogo = screen.getByRole('img', { name: 'TrinaxAI' });
    expect(lightLogo).not.toHaveClass('animate-glow');
    expect(lightLogo.parentElement).toHaveClass(
      'bg-white',
      'shadow-[0_0_14px_1px_rgba(15,23,42,0.14)]',
    );
  });

  it('keeps chat chips compact by default and lets the agent widen the row', () => {
    const chips = [{ label: 'Explicar código', icon: '', action: vi.fn(), idx: 0 }];
    const { rerender } = render(<EmptyChat isDark motd="Hola" rotation={0} chips={chips} />);
    expect(screen.getByRole('button', { name: /explicar código/i }).parentElement).toHaveClass('max-w-md');

    rerender(<EmptyChat isDark motd="Hola" rotation={0} chips={chips} chipsMaxWidth="max-w-4xl" />);
    const row = screen.getByRole('button', { name: /explicar código/i }).parentElement;
    expect(row).toHaveClass('max-w-4xl');
    expect(row).not.toHaveClass('max-w-md');
  });
});
