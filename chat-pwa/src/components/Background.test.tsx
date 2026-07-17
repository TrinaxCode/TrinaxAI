import { fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Background from './Background';

describe('Background animation lifecycle', () => {
  let visibility: DocumentVisibilityState;
  let nextFrameId: number;
  let pendingFrames: Map<number, FrameRequestCallback>;
  let context: CanvasRenderingContext2D;

  beforeEach(() => {
    visibility = 'visible';
    nextFrameId = 1;
    pendingFrames = new Map();

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => visibility,
    });
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      const id = nextFrameId++;
      pendingFrames.set(id, callback);
      return id;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      pendingFrames.delete(id);
    });
    context = {
      arc: vi.fn(),
      beginPath: vi.fn(),
      clearRect: vi.fn(),
      closePath: vi.fn(),
      fill: vi.fn(),
      fillStyle: '',
      lineTo: vi.fn(),
      moveTo: vi.fn(),
      setTransform: vi.fn(),
    } as unknown as CanvasRenderingContext2D;
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (document as unknown as { visibilityState?: DocumentVisibilityState }).visibilityState;
  });

  it('stops requesting frames while hidden and resumes once visible', () => {
    const { unmount } = render(<Background isDark />);
    expect(pendingFrames.size).toBe(1);

    visibility = 'hidden';
    fireEvent(document, new Event('visibilitychange'));
    expect(pendingFrames.size).toBe(0);

    visibility = 'visible';
    fireEvent(document, new Event('visibilitychange'));
    expect(pendingFrames.size).toBe(1);

    unmount();
    expect(pendingFrames.size).toBe(0);
  });

  it('renders a static frame without starting a loop when inactive', () => {
    const { unmount } = render(<Background isDark active={false} />);
    expect(pendingFrames.size).toBe(0);
    unmount();
  });

  it('uses neutral black stars in light mode', () => {
    const fillStyles: string[] = [];
    Object.defineProperty(context, 'fillStyle', {
      configurable: true,
      get: () => fillStyles.at(-1) ?? '',
      set: (value: string) => { fillStyles.push(value); },
    });

    render(<Background isDark={false} variant="stars" active={false} />);

    expect(fillStyles.some((value) => value.startsWith('rgba(0, 0, 0,'))).toBe(true);
    expect(fillStyles.some((value) => value.startsWith('rgba(0, 107, 189,'))).toBe(false);
  });
});
