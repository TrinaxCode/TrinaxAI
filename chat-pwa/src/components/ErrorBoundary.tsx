import { Component, type ErrorInfo, type ReactNode } from 'react';
import { motion } from 'framer-motion';

const ES = {
  title: 'No pudimos mostrar esta sección',
  detail: 'Tus datos están seguros y el resto de TrinaxAI sigue disponible. Recarga para intentarlo de nuevo.',
  reload: 'Recargar',
};
const EN = {
  title: 'We could not display this section',
  detail: 'Your data is safe and the rest of TrinaxAI remains available. Reload to try again.',
  reload: 'Reload',
};

function lang(): 'es' | 'en' {
  try { return localStorage.getItem('tc-lang') === 'en' ? 'en' : 'es'; } catch { return 'es'; }
}

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[TrinaxAI UI] section crashed', error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      const isDark = document.documentElement.classList.contains('dark');
      const strings = lang() === 'en' ? EN : ES;
      return (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className={`h-full flex flex-col items-center justify-center gap-4 px-6 text-center transition-colors duration-300 ${isDark ? 'bg-black' : 'bg-white'}`}
        >
          <p className={`text-sm ${isDark ? 'text-white/50' : 'text-gray-500'}`}>{strings.title}</p>
          <p className={`max-w-md text-xs ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{strings.detail}</p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            className="px-4 py-2 rounded-xl bg-[#006bbd]/20 text-[#006bbd] text-sm hover:bg-[#006bbd]/30 transition-colors"
          >
            {strings.reload}
          </button>
        </motion.div>
      );
    }
    return this.props.children;
  }
}
