import { Component, type ErrorInfo, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { translations, type Lang } from '../i18n/translations';
import ErrorRepairModal from './ErrorRepairModal';

function lang(): Lang {
  try {
    const stored = localStorage.getItem('tc-lang');
    if (stored === 'en' || stored === 'es') return stored;
    return navigator.language?.slice(0, 2).toLowerCase() === 'es' ? 'es' : 'en';
  } catch { return 'en'; }
}

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; repairOpen: boolean; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, repairOpen: false };
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e, repairOpen: false }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[TrinaxAI UI] section crashed', error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      const isDark = document.documentElement.classList.contains('dark');
      const strings = translations[lang()];
      return (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className={`h-full flex flex-col items-center justify-center gap-4 px-6 text-center transition-colors duration-300 ${isDark ? 'bg-black' : 'bg-white'}`}
        >
          <p className={`text-sm ${isDark ? 'text-white/50' : 'text-gray-500'}`}>{strings.errorBoundaryTitle}</p>
          <p className={`max-w-md text-xs ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{strings.errorBoundaryDetail}</p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null, repairOpen: false }); window.location.reload(); }}
            className="px-4 py-2 rounded-xl bg-[#006bbd]/20 text-[#006bbd] text-sm hover:bg-[#006bbd]/30 transition-colors"
          >
            {strings.errorBoundaryReload}
          </button>
          <button
            type="button"
            onClick={() => this.setState({ repairOpen: true })}
            className="text-sm text-[#006bbd] underline underline-offset-2"
          >
            {strings.fixError}
          </button>
          <ErrorRepairModal
            open={this.state.repairOpen}
            dark={isDark}
            title={strings.errorRepairTitle}
            message={strings.errorRepairMessage}
            details={`${strings.errorBoundaryDetail}\n\n${strings.errorRepairHint}`}
            confirmLabel={strings.close}
            showCancel={false}
            onConfirm={() => this.setState({ repairOpen: false })}
            onCancel={() => this.setState({ repairOpen: false })}
          />
        </motion.div>
      );
    }
    return this.props.children;
  }
}
