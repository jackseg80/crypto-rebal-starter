# ✅ Implémentation Flyout Panel - Terminée

## 📦 Fichiers créés

### Composants Web (Shadow DOM)

1. **`static/components/utils.js`** (5.5 KB)
   - Utilitaires partagés
   - `normalizePathname()`, `ns()`, `fetchWithTimeout()`, `fetchRisk()`, `waitForGlobalEventOrTimeout()`, `fallbackSelectors`

2. **`static/components/flyout-panel.js`** (6.8 KB)
   - Web Component UI overlay
   - Handle hover, pin/unpin, Esc close, ARIA complet
   - Responsive : 280px width + 36px handle sous 768px
   - Thème hérité via variables CSS `:host`

3. **`static/components/risk-snapshot.js`** (10.2 KB)
   - Web Component Data
   - Store subscribe (event-based) + polling fallback
   - Affichage : Contradiction, Cap, Fraîcheur, Trend, Régime
   - Loading/error visuels discrets

## 🔧 Fichiers modifiés

### Core

4. **`static/core/risk-dashboard-store.js`** (ligne 626)
   - Émission event `riskStoreReady` après initialisation
   - Permet aux Web Components de se connecter de manière event-based

### Pages HTML

5. **`static/risk-dashboard.html`** (lignes 8697-8704)
   ```html
   <script type="module" src="components/flyout-panel.js"></script>
   <script type="module" src="components/risk-snapshot.js"></script>

   <flyout-panel position="left" width="340" persist-key="risk_dashboard_flyout" pinned>
     <span slot="title">Panneau Risque</span>
     <risk-snapshot slot="content" title="Risk Snapshot" poll-ms="0"></risk-snapshot>
   </flyout-panel>
   ```
   - `poll-ms="0"` → désactive polling (store only)

6. **`static/analytics-unified.html`** (lignes 2176-2183)
   ```html
   <flyout-panel position="left" width="340" persist-key="analytics_flyout">
     <span slot="title">Panneau Risque</span>
     <risk-snapshot slot="content" title="Risk Snapshot" poll-ms="30000"></risk-snapshot>
   </flyout-panel>
   ```
   - `poll-ms="30000"` → polling toutes les 30 secondes

7. **`static/rebalance.html`** (lignes 3475-3482)
   ```html
   <flyout-panel position="left" width="340" persist-key="rebalance_flyout">
     <span slot="title">Panneau Risque</span>
     <risk-snapshot slot="content" title="Risk Snapshot" poll-ms="30000"></risk-snapshot>
   </flyout-panel>
   ```

## 🗑️ Fichiers supprimés

- `static/components/risk-sidebar.js` (legacy)
- `static/components/risk-sidebar.css` (legacy)

## ✅ Fonctionnalités implémentées

### UI (flyout-panel)
- ✅ Handle hover (survol zone gauche → panel apparaît)
- ✅ Pin/Unpin (épingle le panel, état persistant localStorage)
- ✅ Esc close (ferme si non pinned)
- ✅ ARIA complet (`aria-expanded`, `aria-pressed`)
- ✅ Responsive (<768px : 280px width, 36px handle)
- ✅ Thème hérité (variables CSS `--theme-*`)
- ✅ Shadow DOM (isolation CSS complète)

### Data (risk-snapshot)
- ✅ Store subscribe (event-based, attend `riskStoreReady`)
- ✅ Polling fallback (si pas de store, configurable via `poll-ms`)
- ✅ Timeout 5s sur fetch + AbortController
- ✅ Fallback API (`/api/risk/dashboard` → `/api/risk/metrics`)
- ✅ Import sélecteurs (`selectors/governance.js`) avec fallback
- ✅ Affichage : Contradiction (barre), Cap journalier, Fraîcheur (dot), Trend (delta), Régime
- ✅ États visuels : loading (opacity), erreur (⚠ dans trend)
- ✅ Cleanup propre (`unsubscribe`, `clearInterval`)

## 🧪 Tests à effectuer

### Fonctionnels
```bash
# 1. Démarrer le serveur
python -m uvicorn api.main:app --reload --port 8080

# 2. Tester risk-dashboard.html
# URL: http://localhost:8080/static/risk-dashboard.html
# ✓ Panel visible à gauche (pinned par défaut)
# ✓ Données chargées via store (pas de polling)
# ✓ Contradiction, Cap, Fraîcheur affichés
# ✓ Pin/Unpin fonctionne (état persistant après reload)

# 3. Tester analytics-unified.html
# URL: http://localhost:8080/static/analytics-unified.html
# ✓ Handle visible à gauche (48px)
# ✓ Survol handle → panel apparaît
# ✓ Polling toutes les 30s
# ✓ Pin → panel reste affiché
# ✓ Esc → panel se ferme (si non pinned)

# 4. Tester rebalance.html
# URL: http://localhost:8080/static/rebalance.html
# ✓ Même comportement que analytics-unified
```

### Robustesse
```bash
# 1. API 500 → Fallback fonctionne
# Simuler erreur API, vérifier console :
# [risk-snapshot] Primary API failed: ...
# [risk-snapshot] /api/risk/metrics not OK: ...
# → Panel affiche ⚠ dans trend

# 2. Timeout 5s → Pas de blocage
# Simuler latence API > 5s
# → Fetch aborté après 5s, fallback essayé

# 3. JSON malformé → Log warning, valeurs précédentes conservées
# → Console: [risk-snapshot] ...

# 4. Navigation pendant fetch → Pas de crash
# Changer de page rapidement
# → AbortController annule requêtes en cours
```

### Accessibilité
```bash
# 1. Keyboard navigation
# Tab → focus sur handle
# Enter → ouvre panel
# Esc → ferme panel (si non pinned)

# 2. ARIA attributes
# Inspecter DOM Shadow Root :
# <div class="flyout" aria-expanded="true|false">
# <button id="pin" aria-pressed="true|false">
```

### Responsive
```bash
# 1. Mobile (<768px)
# DevTools → Responsive mode 375px width
# ✓ Panel width = 280px (au lieu de 340px)
# ✓ Handle width = 36px (au lieu de 48px)
# ✓ Texte lisible (font-size: 0.875rem)
```

## 🐛 Troubleshooting

### Panel ne s'affiche pas
```javascript
// Vérifier dans la console :
// 1. Event riskStoreReady émis ?
window.addEventListener('riskStoreReady', e => console.log('Store ready!', e.detail));

// 2. Web Components définis ?
console.log(customElements.get('flyout-panel')); // → constructor
console.log(customElements.get('risk-snapshot')); // → constructor

// 3. Shadow DOM créé ?
document.querySelector('flyout-panel').shadowRoot; // → #shadow-root
```

### Données ne se chargent pas
```javascript
// 1. Store disponible ?
console.log(window.riskStore); // → { getState, setState, subscribe }

// 2. API répond ?
fetch('/api/risk/dashboard?min_usd=0').then(r => r.json()).then(console.log);
fetch('/api/risk/metrics').then(r => r.json()).then(console.log);

// 3. Sélecteurs chargés ?
import('../selectors/governance.js').then(console.log);
```

### Thème pas hérité (couleurs par défaut)
```css
/* Vérifier variables CSS parentes */
:root {
  --theme-surface: #0f1115;
  --theme-fg: #e5e7eb;
  --theme-border: #2a2f3b;
}
```

## 📊 Métriques

| Métrique | Valeur |
|----------|--------|
| Fichiers créés | 3 |
| Fichiers modifiés | 4 |
| Fichiers supprimés | 2 |
| Lignes de code ajoutées | ~500 |
| Pages intégrées | 3 (risk-dashboard, analytics-unified, rebalance) |
| Pattern d'intégration | 2 imports + 1 balise = **3 lignes par page** |
| Shadow DOM | ✅ Isolation CSS complète |
| Event-based store | ✅ Plus de busy-loop |
| Fallback API | ✅ Robuste (timeout, retry) |
| Accessibilité | ✅ ARIA complet |
| Responsive | ✅ Mobile-friendly |

## 📋 Option B: Unified Endpoint (Documented, Not Implemented)

**Strategy**: Create `/api/risk/unified` endpoint that returns complete data structure, eliminating need for frontend calculations and conditional hiding.

**Benefits**:
- ✅ All sections visible on all pages
- ✅ Consistent UX everywhere
- ✅ Single source of truth
- ✅ Centralized calculation logic

**Trade-offs**:
- ⚠️ Backend work required (2-3 days dev)
- ⚠️ More complex endpoint (orchestrates multiple APIs)
- ⚠️ Migration/rollout effort (1 week)

**Documentation**: `docs/OPTION_B_UNIFIED_RISK_ENDPOINT.md`

**Decision**: Implement Option B if:
1. Complete data on all pages is critical
2. Team has bandwidth for backend work
3. Long-term maintainability > short-term effort

---

## ⚠️ Known Limitations

1. **Partial Data on Non-Dashboard Pages**:
   - analytics-unified.html and rebalance.html show only 4/10 sections
   - This is expected and acceptable with current implementation
   - Fix: Implement Option B to provide complete data

2. **API Endpoint Mismatch**:
   - `/api/risk/dashboard` returns `risk_metrics`, not `ccs`, `cycle`, `scores`
   - Frontend calculates these on risk-dashboard.html
   - Other pages can't replicate calculations without multiple API calls
   - Fix: Option B unified endpoint

---

## 🚀 Prochaines étapes

1. **Tests utilisateur** : Valider UX sur les 3 pages
2. **Documentation** : Mettre à jour `docs/FRONTEND_PAGES.md`
3. **Mode étendu** (optionnel) : Activer `include-ccs`, `include-onchain`, etc.
4. **Autres pages** : Ajouter flyout sur `execution.html`, `simulations.html`, etc.
5. **Considérer Option B** : Si données complètes nécessaires partout

## 📝 Commits à créer

```bash
git add static/components/utils.js
git commit -m "feat(components): add utils.js (fetchWithTimeout, waitForGlobal, fallbackSelectors)"

git add static/components/flyout-panel.js
git commit -m "feat(components): add flyout-panel web component (overlay, pin, theme)"

git add static/components/risk-snapshot.js
git commit -m "feat(components): add risk-snapshot (store subscribe + polling fallback)"

git add static/core/risk-dashboard-store.js
git commit -m "feat(store): emit riskStoreReady event when initialized"

git add static/risk-dashboard.html
git commit -m "refactor(risk-dashboard): mount unified flyout, remove legacy sidebar"

git add static/analytics-unified.html static/rebalance.html
git commit -m "feat(pages): add risk flyout to analytics-unified and rebalance"

git rm static/components/risk-sidebar.js static/components/risk-sidebar.css
git commit -m "chore(cleanup): remove legacy risk-sidebar components"
```

## ✨ Résultat

**Un seul pattern réutilisable partout** :
```html
<script type="module" src="components/flyout-panel.js"></script>
<script type="module" src="components/risk-snapshot.js"></script>

<flyout-panel position="left" width="340" persist-key="<page>_flyout">
  <span slot="title">Panneau Risque</span>
  <risk-snapshot slot="content" title="Risk Snapshot" poll-ms="30000"></risk-snapshot>
</flyout-panel>
```

**Zero duplication**, **Shadow DOM**, **Event-based**, **Robuste** ! 🎉

