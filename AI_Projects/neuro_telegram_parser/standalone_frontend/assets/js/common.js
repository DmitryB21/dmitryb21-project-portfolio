(() => {
  if (!window.__APP_CONFIG__ || !window.__APP_CONFIG__.API_BASE_URL) {
    console.warn('env.js: window.__APP_CONFIG__.API_BASE_URL не задан. Используется http://127.0.0.1:5000');
    window.__APP_CONFIG__ = window.__APP_CONFIG__ || {};
    window.__APP_CONFIG__.API_BASE_URL = 'http://127.0.0.1:5000';
  }
})();

async function apiGet(path) {
  const base = window.__APP_CONFIG__.API_BASE_URL.replace(/\/+$/, '');
  const url = `${base}${path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function formatNumber(n) {
  if (n == null) return '0';
  return new Intl.NumberFormat('ru-RU').format(n);
}

function escapeHtml(s) {
  if (!s) return '';
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}


