import { useEffect, useRef, memo } from 'react';

interface BackgroundProps {
  isDark: boolean;
  /** 'waves' (default) draws the flowing wave layers; 'stars' draws a twinkling starfield for agent mode. */
  variant?: 'waves' | 'stars';
  /** Keep a static first frame while an opaque screen covers the background. */
  active?: boolean;
}

const MAX_CANVAS_PIXELS = 2_100_000;
const LOW_POWER_CANVAS_PIXELS = 1_050_000;

const Background = memo(function Background({ isDark, variant = 'waves', active = true }: BackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const visibleRef = useRef(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let resizeFrame = 0;
    let disposed = false;
    visibleRef.current = document.visibilityState === 'visible';

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
    const deviceMemory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
    const lowPowerDevice = Boolean(
      connection?.saveData
      || (typeof deviceMemory === 'number' && deviceMemory <= 2)
      || navigator.hardwareConcurrency <= 2,
    );
    const shouldAnimate = () => active && !reducedMotion?.matches && !connection?.saveData;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const pixelBudget = lowPowerDevice ? LOW_POWER_CANVAS_PIXELS : MAX_CANVAS_PIXELS;
      const budgetDpr = Math.sqrt(pixelBudget / Math.max(1, width * height));
      dpr = Math.max(0.5, Math.min(window.devicePixelRatio || 1, 1.5, budgetDpr));
      canvas!.width = Math.max(1, Math.round(width * dpr));
      canvas!.height = Math.max(1, Math.round(height * dpr));
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // --- Wave layers (default background) ---
    const layers: [number, number, number, number, number, number, number, number][] = [
      // baseY, amp, freq, speed, alpha, r, g, b
      [0.62, 80, 0.005, 0.0003, 0.16, 0, 107, 189],
      [0.70, 60, 0.008, 0.0005, 0.12, 0, 130, 210],
      [0.78, 90, 0.004, 0.0004, 0.10, 0, 80, 160],
      [0.86, 50, 0.010, 0.0006, 0.08, 10, 140, 220],
      [0.94, 70, 0.006, 0.00035, 0.06, 0, 107, 189],
    ];

    // --- Star field (agent mode) ---
    // Deterministic pseudo-random so stars stay stable across resizes without Math.random churn.
    let stars: { x: number; y: number; r: number; base: number; twSpeed: number; twPhase: number }[] = [];
    function seedStars() {
      const count = Math.min(160, Math.round((width * height) / 9000));
      stars = [];
      let s = 1337;
      const rand = () => {
        s = (s * 1103515245 + 12345) & 0x7fffffff;
        return s / 0x7fffffff;
      };
      for (let i = 0; i < count; i += 1) {
        stars.push({
          x: rand() * width,
          y: rand() * height,
          r: rand() * 1.3 + 0.3,
          base: rand() * 0.5 + 0.3,
          twSpeed: rand() * 0.0016 + 0.0004,
          twPhase: rand() * Math.PI * 2,
        });
      }
    }

    let lastFrame = 0;
    const FPS = lowPowerDevice ? 15 : 24;
    const frameInterval = 1000 / FPS;

    function drawWaves(now: number) {
      ctx!.clearRect(0, 0, width, height);

      for (const [baseY, amp, freq, speed, alpha, lr, lg, lb] of layers) {
        ctx!.beginPath();
        const y0 = height * baseY;
        const elapsed = now;

        // Step of 4px instead of 2px — halves the path point count.
        for (let x = -1; x <= width + 2; x += 4) {
          const y =
            y0 +
            Math.sin(x * freq + elapsed * speed) * amp +
            Math.cos(x * freq * 0.7 + elapsed * speed * 1.3) * amp * 0.5;
          if (x === -1) {
            ctx!.moveTo(x, y);
          } else {
            ctx!.lineTo(x, y);
          }
        }

        ctx!.lineTo(width + 2, height + 10);
        ctx!.lineTo(-2, height + 10);
        ctx!.closePath();

        const adjustedAlpha = isDark ? alpha : alpha * 0.55;
        ctx!.fillStyle = `rgba(${lr}, ${lg}, ${lb}, ${adjustedAlpha})`;
        ctx!.fill();
      }
    }

    function drawStars(now: number) {
      ctx!.clearRect(0, 0, width, height);
      // Keep the dark starfield unchanged; light mode uses neutral black so
      // the Agent identity follows the navigation icon palette.
      const tint = isDark ? '255, 255, 255' : '0, 0, 0';
      for (const star of stars) {
        const twinkle = 0.5 + 0.5 * Math.sin(now * star.twSpeed + star.twPhase);
        const alpha = star.base * twinkle * (isDark ? 1 : 0.6);
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, star.r, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(${tint}, ${alpha})`;
        ctx!.fill();
        // Occasional soft glow on the larger stars.
        if (star.r > 1.1) {
          ctx!.beginPath();
          ctx!.arc(star.x, star.y, star.r * 2.5, 0, Math.PI * 2);
          ctx!.fillStyle = `rgba(${tint}, ${alpha * 0.12})`;
          ctx!.fill();
        }
      }
    }

    const draw = variant === 'stars' ? drawStars : drawWaves;

    function queueAnimation() {
      if (disposed || rafRef.current || !visibleRef.current || !shouldAnimate()) return;
      rafRef.current = window.requestAnimationFrame(animate);
    }

    function animate(now: number) {
      rafRef.current = 0;
      if (disposed || !visibleRef.current || !shouldAnimate()) return;
      if (now - lastFrame < frameInterval) {
        queueAnimation();
        return;
      }
      lastFrame = now;
      draw(now);
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
    document.addEventListener('visibilitychange', onVisibility);

    function onResize() {
      window.cancelAnimationFrame(resizeFrame);
      resizeFrame = window.requestAnimationFrame(() => {
        resizeFrame = 0;
        resize();
        if (variant === 'stars') seedStars();
        draw(performance.now());
      });
    }

    const onMotionPreferenceChange = () => {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
      draw(performance.now());
      queueAnimation();
    };

    resize();
    if (variant === 'stars') seedStars();
    // Paint the first frame immediately so the background is visible on first
    // render instead of waiting for the first throttled animation tick.
    draw(0);
    window.addEventListener('resize', onResize);
    reducedMotion?.addEventListener?.('change', onMotionPreferenceChange);
    queueAnimation();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(rafRef.current);
      window.cancelAnimationFrame(resizeFrame);
      rafRef.current = 0;
      window.removeEventListener('resize', onResize);
      document.removeEventListener('visibilitychange', onVisibility);
      reducedMotion?.removeEventListener?.('change', onMotionPreferenceChange);
    };
  }, [active, isDark, variant]);

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
