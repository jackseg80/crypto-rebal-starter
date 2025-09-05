// Gestion des onglets pour analytics-unified
document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('#analytics-tabs .tab-btn');
  const panels = Array.from(document.querySelectorAll('.tab-panel'));

  const activate = (targetSel) => {
    tabs.forEach(t => t.classList.remove('active'));
    panels.forEach(p => p.classList.remove('active'));
    const btn = Array.from(tabs).find(b => b.dataset.target === targetSel);
    const panel = document.querySelector(targetSel);
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');
    // Mémoriser l'onglet actif
    try { localStorage.setItem('analytics_active_tab', targetSel); } catch {}
  };

  tabs.forEach(btn => btn.addEventListener('click', () => activate(btn.dataset.target)));

  // Restaurer l'onglet mémorisé
  try {
    const saved = localStorage.getItem('analytics_active_tab');
    if (saved && document.querySelector(saved)) activate(saved);
  } catch {}
});

