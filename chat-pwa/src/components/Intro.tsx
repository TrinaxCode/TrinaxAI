import { useEffect, useState, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { getPreferredUserName } from '../lib/userProfile';

interface IntroProps {
  onFinish: () => void;
}

const Intro = memo(function Intro({ onFinish }: IntroProps) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const [visible, setVisible] = useState(true);
  const displayName = getPreferredUserName(lang);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
    }, 2200);
    const finishTimer = setTimeout(onFinish, 2600); // 2200 + 400
    return () => {
      clearTimeout(timer);
      clearTimeout(finishTimer);
    };
  }, [onFinish]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className={`fixed inset-0 z-50 flex flex-col items-center justify-center ${isDark ? 'bg-black' : 'bg-white'}`}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: 'easeInOut' }}
        >
          {/* Logo — larger & striking with glow */}
          <motion.img
            src="/logo-of-app.webp"
            alt="TrinaxAI"
            className="w-32 h-32 md:w-40 md:h-40 mb-10 rounded-2xl shadow-2xl
                       shadow-[#006bbd]/20 animate-glow"
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              duration: 1.0,
              ease: [0.16, 1, 0.3, 1],
            }}
          />

          {/* Title */}
          <motion.h1
            className={`max-w-[90vw] text-center text-3xl sm:text-4xl md:text-5xl font-light tracking-normal ${isDark ? 'text-white' : 'text-gray-900'}`}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.8,
              delay: 0.35,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            {t('welcome')}{' '}
            <span className="font-semibold text-[#006bbd] break-words">{displayName}</span>
          </motion.h1>

          {/* Animated loading line */}
          <motion.div
            className="mt-10 h-[1px] bg-gradient-to-r from-transparent via-[#006bbd]/60 to-transparent"
            initial={{ width: 0 }}
            animate={{ width: 120 }}
            transition={{ duration: 1.4, delay: 0.6, ease: 'easeInOut' }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
});
export default Intro;
