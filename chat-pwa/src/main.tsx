import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { useRegisterSW } from 'virtual:pwa-register/react';
import { ThemeProvider } from './theme/ThemeContext';
import { I18nProvider } from './i18n/I18nContext';
import { ToastProvider } from './components/Toast';
import App from './App';
import PwaUpdater from './components/PwaUpdater';
import './index.css';

if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout !== 'function') {
  AbortSignal.timeout = (ms: number) => {
    const controller = new AbortController();
    window.setTimeout(() => controller.abort(), ms);
    return controller.signal;
  };
}

function Root() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_swUrl, r) {
      if (r) {
        setInterval(async () => {
          if (r.installing || r.waiting) return;
          await r.update();
        }, 60 * 60 * 1000);
      }
    },
  });

  const handleRefresh = () => {
    updateServiceWorker(true).then(() => {
      setNeedRefresh(false);
    });
  };

  return (
    <StrictMode>
      <ThemeProvider>
        <I18nProvider>
          <ToastProvider>
            <App />
            <PwaUpdater needsUpdate={needRefresh} onRefresh={handleRefresh} />
          </ToastProvider>
        </I18nProvider>
      </ThemeProvider>
    </StrictMode>
  );
}

createRoot(document.getElementById('root')!).render(<Root />);
