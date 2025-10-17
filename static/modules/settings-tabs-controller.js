// Tabs logic
(function () {
  const btns = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');
  function activate(target) {
    btns.forEach(b => b.classList.toggle('active', b.getAttribute('data-target') === `#${target.id}`));
    panels.forEach(p => p.classList.toggle('active', p === target));
    history.replaceState(null, '', `#${target.id}`);
  }
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      const sel = btn.getAttribute('data-target');
      const target = document.querySelector(sel);
      if (target) {
        activate(target);
      }
    })
  });
  // Deep link support via hash
  const hash = location.hash && document.querySelector(location.hash);
  if (hash && hash.classList.contains('tab-panel')) activate(hash);
})();

// Appliquer le thème dès le chargement de global-config.js
setTimeout(() => {
  if (window.globalConfig && window.globalConfig.applyTheme) {
    console.debug('Early theme application...');
    window.globalConfig.applyTheme();
  }
  if (window.applyAppearance) {
    window.applyAppearance();
  }
}, 0);
