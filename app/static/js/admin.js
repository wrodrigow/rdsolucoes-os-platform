/* RD Soluções OS — Admin Panel JS */

// ── Sidebar toggle (mobile) ───────────────────────────────────────
const sidebarToggle = document.getElementById('adm-sidebar-toggle');
const sidebar = document.querySelector('.adm-sidebar');
if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  });
}

// ── Bar chart rendering ───────────────────────────────────────────
function renderBarChart(containerId, data) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const max = Math.max(...data.map(d => d.value), 1);
  container.innerHTML = '';
  data.forEach(d => {
    const pct = Math.round((d.value / max) * 100);
    const item = document.createElement('div');
    item.className = 'adm-chart-bar-item';
    item.innerHTML = `
      <span class="adm-chart-bar-value">${d.label2 || ''}</span>
      <div class="adm-chart-bar-fill" style="height:${Math.max(pct, 4)}%"></div>
      <span class="adm-chart-bar-label">${d.label}</span>
    `;
    container.appendChild(item);
  });
}

// ── Confirm dialogs ───────────────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// ── Auto-dismiss alerts ───────────────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.adm-alert.auto-dismiss').forEach(el => {
    el.style.transition = 'opacity 0.5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  });
}, 4000);

// ── Copy to clipboard ─────────────────────────────────────────────
document.querySelectorAll('[data-copy]').forEach(btn => {
  btn.addEventListener('click', () => {
    const text = btn.dataset.copy;
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.innerHTML;
      btn.innerHTML = '✓ Copiado!';
      btn.classList.add('adm-btn-success');
      setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('adm-btn-success'); }, 2000);
    });
  });
});

// ── Keys import preview ───────────────────────────────────────────
const keysTexto = document.getElementById('keys_texto');
const keysCount = document.getElementById('keys_count');
if (keysTexto && keysCount) {
  keysTexto.addEventListener('input', () => {
    const linhas = keysTexto.value.split('\n').filter(l => l.trim().length === 19 && l.trim().split('-').length === 4);
    keysCount.textContent = `${linhas.length} keys detectadas`;
  });
}

// ── File upload preview ───────────────────────────────────────────
const fileInput = document.getElementById('arquivo');
const fileLabel = document.getElementById('file-label');
if (fileInput && fileLabel) {
  fileInput.addEventListener('change', () => {
    const f = fileInput.files[0];
    if (f) {
      const mb = (f.size / 1048576).toFixed(1);
      fileLabel.textContent = `${f.name} (${mb} MB)`;
    }
  });
}
