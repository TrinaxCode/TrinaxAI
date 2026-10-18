(function () {
  var theme;

  try {
    var stored = localStorage.getItem('tc-theme');
    if (stored === 'light' || stored === 'dark') theme = stored;
    if (stored === 'sepia' || stored === 'contrast') theme = 'dark';
  } catch (_) {
    // Storage can be unavailable in privacy-restricted browsers.
  }

  if (!theme) {
    theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light'
      : 'dark';
  }

  var root = document.documentElement;
  root.classList.remove('dark', 'light');
  root.classList.add(theme);

  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#000000' : '#ffffff');

  var appleMeta = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  if (appleMeta) appleMeta.setAttribute('content', theme === 'dark' ? 'black-translucent' : 'default');
})();
