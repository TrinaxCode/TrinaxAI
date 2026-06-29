import { Component, type ReactNode } from 'react';

const ES = { title: '⚠️ Algo salió mal', reload: 'Recargar' };
const EN = { title: '⚠️ Something went wrong', reload: 'Reload' };

function lang(): 'es' | 'en' {
  try { return localStorage.getItem('tc-lang') === 'en' ? 'en' : 'es'; } catch { return 'es'; }
}

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e }; }
  render() {
    if (this.state.hasError) {
      const isDark = document.documentElement.classList.contains('dark');
      const strings = lang() === 'en' ? EN : ES;
      return (
        <div className={`h-full flex flex-col items-center justify-center gap-4 px-6 text-center ${isDark ? 'bg-black' : 'bg-white'}`}>
          <p className={`text-sm ${isDark ? 'text-white/50' : 'text-gray-500'}`}>{strings.title}</p>
          <p className={`text-xs ${isDark ? 'text-white/20' : 'text-gray-400'}`}>{this.state.error?.message}</p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            className="px-4 py-2 rounded-xl bg-[#006bbd]/20 text-[#006bbd] text-sm"
          >
            {strings.reload}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
