import { useEffect, useRef, memo } from 'react';

interface BackgroundProps { isDark: boolean; }

const Background = memo(function Background({ isDark }: BackgroundProps) {
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

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(1, 0, 0, 1, 0, 0);
      ctx!.scale(dpr, dpr);
    }

    const layers: [number, number, number, number, number, number, number, number][] = [
      // baseY, amp, freq, speed, alpha, r, g, b
      [0.62, 80, 0.005, 0.0003, 0.16, 0, 107, 189],
      [0.70, 60, 0.008, 0.0005, 0.12, 0, 130, 210],
      [0.78, 90, 0.004, 0.0004, 0.10, 0, 80, 160],
      [0.86, 50, 0.010, 0.0006, 0.08, 10, 140, 220],
      [0.94, 70, 0.006, 0.00035, 0.06, 0, 107, 189],
    ];

    const darkColor = [0, 107, 189];
    const lightColor = [30, 144, 220];

    let lastFrame = 0;
    const FPS = 30;
    const frameInterval = 1000 / FPS;

    function draw(now: number) {
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

    function animate(now: number) {
      if (!visibleRef.current || !canvas || !ctx) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }
      // Throttle to ~30 FPS instead of 60 FPS
      if (now - lastFrame < frameInterval) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }
      lastFrame = now;
      draw(now);
      rafRef.current = requestAnimationFrame(animate);
    }

    const onVisibility = () => {
      visibleRef.current = document.visibilityState === 'visible';
    };
    document.addEventListener('visibilitychange', onVisibility);

    resize();
    window.addEventListener('resize', resize);
    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [isDark]);

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
