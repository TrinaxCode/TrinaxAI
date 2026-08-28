(() => {
  const retry = document.getElementById('retry');
  retry?.addEventListener('click', () => window.location.reload());

  let language = 'en';
  try {
    const stored = localStorage.getItem('tc-lang');
    language = stored === 'es'
      ? 'es'
      : (navigator.language || '').toLowerCase().startsWith('es') ? 'es' : 'en';
  } catch {
    // The English offline copy is a safe fallback when storage is unavailable.
  }
  if (language !== 'es') return;

  document.documentElement.lang = 'es';
  document.title = 'Sin conexión - TrinaxAI';
  const title = document.getElementById('title');
  const message = document.getElementById('message');
  if (title) title.textContent = 'Sin conexión';
  if (message) {
    message.textContent = 'No se puede alcanzar el equipo donde corre TrinaxAI. Vuelve a conectarte a ese equipo, a su red local o a tu VPN e inténtalo de nuevo.';
  }
  if (retry) retry.textContent = 'Reintentar';
})();
