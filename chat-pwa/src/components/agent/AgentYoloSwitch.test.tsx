import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AgentYoloSwitch from './AgentYoloSwitch';

const host = vi.hoisted(() => ({ local: true }));
vi.mock('../../lib/authHeaders', () => ({ isLocalHostBrowser: () => host.local }));

const props = { enabled: false, disabled: false, onChange: () => undefined, isDark: true, t: (key: string) => key };

describe('AgentYoloSwitch', () => {
  afterEach(() => { host.local = true; });

  it('is offered on the localhost host', () => {
    render(<AgentYoloSwitch {...props} />);
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('is hidden on a paired device so every dangerous action keeps asking', () => {
    host.local = false;
    const { container } = render(<AgentYoloSwitch {...props} />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
  });
});
