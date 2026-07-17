import { useEffect, useState, memo } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { getPreferredUserName } from '../lib/userProfile';

interface IntroProps {
  onFinish: () => void;
}

// The splash animates with pure CSS (compositor-driven opacity/transform), NOT
// framer-motion. This is deliberate: the heavy chat UI mounts on the main
// thread behind this opaque splash, and a main-thread animation loop (which
// framer-motion uses) would stutter during that ~0.2s mount. Compositor
// animations keep running smoothly regardless of main-thread work.
const Intro = memo(function Intro({ onFinish }: IntroProps) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const [leaving, setLeaving] = useState(false);
  const displayName = getPreferredUserName(lang);

  useEffect(() => {
    const timer = setTimeout(() => setLeaving(true), 2200);
    const finishTimer = setTimeout(onFinish, 2600); // 2200 + 400 fade-out
    return () => {
      clearTimeout(timer);
      clearTimeout(finishTimer);
    };
  }, [onFinish]);

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center ${
        isDark ? 'bg-black' : 'bg-white'
      } ${leaving ? 'animate-intro-out' : ''}`}
    >
      {/* Logo — larger & striking with glow */}
      <img
        src="/logo-of-app.webp"
        alt="TrinaxAI"
        width={160}
        height={160}
        className="animate-intro-logo animate-glow w-32 h-32 md:w-40 md:h-40 mb-10
                   rounded-2xl shadow-2xl shadow-[#006bbd]/20"
      />

      {/* Title */}
      <h1
        className={`animate-intro-title max-w-[90vw] text-center text-3xl sm:text-4xl md:text-5xl font-light tracking-normal ${
          isDark ? 'text-white' : 'text-gray-900'
        }`}
      >
        {t('welcome')}{' '}
        <span className="font-semibold text-[#006bbd] break-words">{displayName}</span>
      </h1>

      {/* Animated loading line (scaleX on the compositor) */}
      <div className="animate-intro-line mt-10 h-[1px] w-[120px] origin-center bg-gradient-to-r from-transparent via-[#006bbd]/60 to-transparent" />
    </div>
  );
});
export default Intro;
