import { Component, type ErrorInfo, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { MdErrorOutline } from 'react-icons/md';
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
          className={`grid h-full place-items-center px-6 transition-colors duration-300 ${isDark ? 'bg-[#0b111a]' : 'bg-[#f7f9fc]'}`}
        >
          <div className={`w-full max-w-md rounded-2xl border p-7 text-center ${isDark ? 'border-white/10 bg-[#14202d]' : 'border-slate-200 bg-white'}`}>
            <span className={`mx-auto grid h-14 w-14 place-items-center rounded-2xl ${isDark ? 'bg-sky-400/10 text-sky-400' : 'bg-sky-50 text-[#006bbd]'}`} aria-hidden="true"><MdErrorOutline size={28} /></span>
            <h1 className={`mt-5 text-lg font-semibold ${isDark ? 'text-white/90' : 'text-slate-800'}`}>{strings.errorBoundaryTitle}</h1>
            <p className={`mt-2 text-sm leading-relaxed ${isDark ? 'text-white/60' : 'text-slate-600'}`}>{strings.errorBoundaryDetail}</p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={() => { this.setState({ hasError: false, error: null, repairOpen: false }); window.location.reload(); }}
                className="min-h-10 rounded-xl bg-[#006bbd] px-4 text-sm font-medium text-white transition-colors hover:bg-[#0059a0]"
              >
                {strings.errorBoundaryReload}
              </button>
              <button
                type="button"
                onClick={() => this.setState({ repairOpen: true })}
                className={`min-h-10 px-2 text-sm underline underline-offset-2 ${isDark ? 'text-sky-400' : 'text-[#006bbd]'}`}
              >
                {strings.fixError}
              </button>
            </div>
          </div>
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
