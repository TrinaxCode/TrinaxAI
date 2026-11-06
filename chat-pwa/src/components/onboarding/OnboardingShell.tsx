import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

import './onboarding.css';

interface Props {
  children: ReactNode;
  className?: string;
}

/**
 * First-run frame: the TrinaxAI mark on its own, above one panel, floating over
 * the app's animated Background (this layer is deliberately transparent).
 */
export default function OnboardingShell({ children, className = 'z-50' }: Props) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className={`onb-root fixed inset-0 overflow-y-auto ${className}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.16, 1, 0.3, 1] }}
    >
      <main
        className="mx-auto flex min-h-full w-full max-w-md flex-col items-center justify-center gap-5 px-4 py-8"
        style={{
          paddingTop: 'max(2rem, calc(env(safe-area-inset-top, 0px) + 1rem))',
          paddingBottom: 'max(2rem, calc(env(safe-area-inset-bottom, 0px) + 1rem))',
        }}
      >
        <motion.img
          src="/logo-for-ai-transparent.webp"
          alt="TrinaxAI"
          translate="no"
          width={96}
          height={96}
          draggable={false}
          className="onb-logo"
          initial={reduceMotion ? false : { opacity: 0, y: -8, scale: 0.94 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        />
        <section className="onb-panel w-full p-6 sm:p-8">{children}</section>
      </main>
    </motion.div>
  );
}
