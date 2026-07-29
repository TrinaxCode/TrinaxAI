import { memo, useEffect, useRef } from 'react';

interface BackgroundProps {
  isDark: boolean;
  /** Keep a static first frame while an opaque screen covers the background. */
  active?: boolean;
}

const MAX_CANVAS_PIXELS = 2_100_000;
const LOW_POWER_CANVAS_PIXELS = 1_050_000;

const Background = memo(function Background({ isDark, active = true }: BackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);
  const visibleRef = useRef(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const backgroundCanvas = canvas;
    const context = ctx;

    let width = 0;
    let height = 0;
    let resizeFrame = 0;
    let lastFrame = 0;
    let disposed = false;
    visibleRef.current = document.visibilityState === 'visible';

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
    const deviceMemory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
    const lowPowerDevice = Boolean(
      connection?.saveData
      || (typeof deviceMemory === 'number' && deviceMemory <= 2)
      || navigator.hardwareConcurrency <= 2
    );
    const frameInterval = 1000 / (lowPowerDevice ? 15 : 24);
    const shouldAnimate = () => active && !reducedMotion?.matches && !connection?.saveData;
    const layers: [number, number, number, number, number, number, number, number][] = [
      [0.62, 80, 0.005, 0.0003, 0.16, 0, 107, 189],
      [0.70, 60, 0.008, 0.0005, 0.12, 0, 130, 210],
      [0.78, 90, 0.004, 0.0004, 0.10, 0, 80, 160],
      [0.86, 50, 0.010, 0.0006, 0.08, 10, 140, 220],
      [0.94, 70, 0.006, 0.00035, 0.06, 0, 107, 189],
    ];

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const pixelBudget = lowPowerDevice ? LOW_POWER_CANVAS_PIXELS : MAX_CANVAS_PIXELS;
      const budgetDpr = Math.sqrt(pixelBudget / Math.max(1, width * height));
      const dpr = Math.max(0.5, Math.min(window.devicePixelRatio || 1, 1.5, budgetDpr));
      backgroundCanvas.width = Math.max(1, Math.round(width * dpr));
      backgroundCanvas.height = Math.max(1, Math.round(height * dpr));
      backgroundCanvas.style.width = `${width}px`;
      backgroundCanvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function draw(now: number) {
      context.clearRect(0, 0, width, height);

      for (const [baseY, amplitude, frequency, speed, alpha, red, green, blue] of layers) {
        context.beginPath();
        const y0 = height * baseY;
        for (let x = -1; x <= width + 2; x += 4) {
          const y = y0
            + Math.sin(x * frequency + now * speed) * amplitude
            + Math.cos(x * frequency * 0.7 + now * speed * 1.3) * amplitude * 0.5;
          if (x === -1) context.moveTo(x, y);
          else context.lineTo(x, y);
        }
        context.lineTo(width + 2, height + 10);
        context.lineTo(-2, height + 10);
        context.closePath();
        context.fillStyle = `rgba(${red}, ${green}, ${blue}, ${isDark ? alpha : alpha * 0.55})`;
        context.fill();
      }
    }

    function queueAnimation() {
      if (disposed || rafRef.current || !visibleRef.current || !shouldAnimate()) return;
      rafRef.current = window.requestAnimationFrame(animate);
    }

    function animate(now: number) {
      rafRef.current = 0;
      if (disposed || !visibleRef.current || !shouldAnimate()) return;
      if (now - lastFrame >= frameInterval) {
        lastFrame = now;
        draw(now);
      }
      queueAnimation();
    }

    const onVisibility = () => {
      visibleRef.current = document.visibilityState === 'visible';
      if (!visibleRef.current) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
        return;
      }
      lastFrame = 0;
      draw(performance.now());
      queueAnimation();
    };

    const onResize = () => {
      window.cancelAnimationFrame(resizeFrame);
      resizeFrame = window.requestAnimationFrame(() => {
        resizeFrame = 0;
        resize();
        draw(performance.now());
      });
    };

    const onMotionPreferenceChange = () => {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
      draw(performance.now());
      queueAnimation();
    };

    resize();
    draw(0);
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('resize', onResize);
    reducedMotion?.addEventListener?.('change', onMotionPreferenceChange);
    queueAnimation();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(rafRef.current);
      window.cancelAnimationFrame(resizeFrame);
      rafRef.current = 0;
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('resize', onResize);
      reducedMotion?.removeEventListener?.('change', onMotionPreferenceChange);
    };
  }, [active, isDark]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: 0 }}
      aria-hidden="true"
    />
  );
});

export default Background;
