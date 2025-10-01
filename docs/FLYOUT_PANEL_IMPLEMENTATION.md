# Flyout Panel Implementation

## Vue d'ensemble

Le système de **Flyout Panel** permet d'afficher une **sidebar Risk unifiée** accessible depuis n'importe quelle page du dashboard, avec un mécanisme de survol/pin et un affichage identique partout.

## Architecture

### Composants

1. **`static/components/flyout-panel.js`**
   - Gère la mécanique du flyout (show/hide, pin, push layout)
   - `createFlyoutPanel(options)` - fonction principale
   - Feature flag requis : `localStorage.setItem('__ui.flyout.enabled', '1')`

2. **`static/components/flyout-panel.css`**
   - Styles pour le flyout (transform, animations, handle)

3. **`static/components/risk-sidebar.js`**
   - Génère le HTML de la sidebar Risk (identique à `risk-dashboard.html`)
   - `createRiskSidebar(container)` - génère le HTML + charge les données
   - Fonctionne standalone sur toutes les pages

4. **`static/components/risk-sidebar.css`**
   - Styles pour les éléments de la sidebar (gauges, scores, status indicators)

### Pages intégrées

| Page | Status | Implémentation |
|------|--------|----------------|
| `risk-dashboard.html` | ✅ **HTML statique** | Sidebar intégrée (lignes 2106-2240), pas de flyout |
| `analytics-unified.html` | ✅ **Flyout dynamique** | Utilise `risk-sidebar.js` + `flyout-panel.js` |
| `rebalance.html` | ✅ **Flyout dynamique** | Utilise `risk-sidebar.js` + `flyout-panel.js` |
| `archive/demos/execution.html` | ✅ **Flyout dynamique** | Utilise `risk-sidebar.js` + `flyout-panel.js` |

## Utilisation

### Activer le feature flag

```javascript
localStorage.setItem('__ui.flyout.enabled', '1');
```

**Page de test** : [/static/test-flyout-setup.html](/static/test-flyout-setup.html)

### Intégrer sur une nouvelle page

```html
<!-- CSS -->
<link rel="stylesheet" href="/static/components/flyout-panel.css">
<link rel="stylesheet" href="/static/components/risk-sidebar.css">

<!-- JavaScript -->
<script type="module">
  import { createFlyoutPanel } from '/static/components/flyout-panel.js';
  import { createRiskSidebar } from '/static/components/risk-sidebar.js';

  document.addEventListener('DOMContentLoaded', () => {
    // 1. Créer un conteneur caché pour la sidebar
    const sidebarContainer = document.createElement('div');
    sidebarContainer.className = 'sidebar risk-sidebar-source';
    sidebarContainer.style.display = 'none';
    document.body.appendChild(sidebarContainer);

    // 2. Générer le contenu de la sidebar
    createRiskSidebar(sidebarContainer);

    // 3. Initialiser le flyout
    createFlyoutPanel({
      sourceSelector: '.risk-sidebar-source',
      title: '🎯 Risk Snapshot',
      handleText: '🎯 Risk',
      persistKey: 'ma_page',  // Unique par page
      removeToggleButton: true,
      pushContainers: ['.wrap', '.container'],  // Containers à décaler quand pinned
      baseOffset: 40,
      pinnedOffset: 340
    });
  });
</script>
```

## Chargement des données

### Sur `risk-dashboard.html`

Les données sont chargées par la fonction `refreshDashboard()` existante, qui appelle `updateSidebar(state)` pour mettre à jour le HTML statique.

### Sur les autres pages (flyout)

Le composant `risk-sidebar.js` charge les données de manière autonome :

1. **Détection** : Vérifie si on est sur `risk-dashboard.html`
2. **Standalone** : Si non, lance `refreshSidebarData()` qui fetch les APIs :
   - `/api/risk/metrics` - Scores (CCS, On-Chain, Risk, Blended)
   - `/execution/governance/status` - Statut governance
   - `/api/alerts?limit=5&status=active` - Alertes actives
3. **Rafraîchissement** : Toutes les 30 secondes

### APIs utilisées

```javascript
// Scores
GET /api/risk/metrics
{
  "cycle": { "ccsStar": 80, "phase": "Bull", "months": 18 },
  "scores": { "onchain": 75, "risk": 65, "blended": 72 },
  "regime": { "phase": "Bull Market" },
  "decision": { "confidence": 0.85, "contradiction": 0.12 }
}

// Governance
GET /execution/governance/status
{
  "mode": "auto",
  "contradiction": 0.12,
  "constraints": { "market_cap": true }
}

// Alertes
GET /api/alerts?limit=5&status=active
{
  "alerts": [
    {
      "type": "High Risk",
      "message": "Portfolio concentration > 50%",
      "severity": "high",
      "status": "active"
    }
  ]
}
```

## Comportement

### Flyout

- **Hover** : Survol de la zone gauche (40px) → sidebar apparaît
- **Pin** : Clic sur 📌 → sidebar reste affichée, layout se décale
- **Unpin** : Clic sur ❌ → sidebar se cache, layout revient
- **Persistance** : État pin/unpin sauvegardé dans `localStorage` par page

### Layout Push

Quand la sidebar est **pinned**, les containers spécifiés dans `pushContainers` sont décalés de `pinnedOffset` pixels vers la droite, évitant le chevauchement.

## Structure HTML générée

La sidebar contient (dans l'ordre) :

1. **CCS Mixte** - Score directeur du marché
2. **On-Chain Composite** - Score on-chain
3. **Risk Score** - Score de risque portfolio
4. **Blended Decision Score** - Score décisionnel synthétique (grande card)
5. **Market Regime** - Régime de marché (Bull/Neutral/Risk-Off)
6. **Cycle Position** - Position dans le cycle Bitcoin
7. **Target Changes** - Changements de targets
8. **API Health** - Santé des APIs (Backend, Signals)
9. **Governance** - Statut governance (mode, contradiction, contraintes)
10. **Active Alerts** - Alertes actives (max 5) + lien vers historique

## Code couleurs

### Scores (data-score attribute)

- **Excellent** (≥80) : Vert
- **Bon** (60-79) : Vert clair
- **Neutre** (40-59) : Jaune
- **Faible** (20-39) : Orange
- **Critique** (<20) : Rouge

### Status Dots

- **Active** : Vert (système OK, bull market)
- **Neutral** : Bleu (neutre, idle)
- **Warning** : Orange (attention requise)
- **Critical** : Rouge (erreur, risk-off, frozen)

### Alertes

- **Critical** : Rouge
- **High** : Orange
- **Medium** : Orange
- **Low** : Bleu

## Troubleshooting

### Le flyout n'apparaît pas

1. ✅ Vérifier le feature flag : `localStorage.getItem('__ui.flyout.enabled') === '1'`
2. ✅ Vérifier la console : erreurs d'import ?
3. ✅ Vérifier que les CSS sont chargés (DevTools > Network)

### Les données ne se chargent pas

1. ✅ Vérifier les APIs dans la console réseau
2. ✅ Vérifier les CORS (backend doit autoriser `/static/*`)
3. ✅ Vérifier les logs console : `[Risk Sidebar] ...`

### risk-dashboard.html ne fonctionne plus

1. ✅ Vérifier que le HTML statique est présent (lignes 2106-2240)
2. ✅ Vérifier que `createRiskSidebar()` n'est PAS appelé sur cette page
3. ✅ Vérifier que `refreshDashboard()` et `updateSidebar()` fonctionnent

### Les scores affichent tous "--"

1. ✅ Attendre 30s (premier refresh)
2. ✅ Vérifier que `/api/risk/metrics` répond (200)
3. ✅ Vérifier la structure de la réponse JSON

## Historique

- **2025-10-01** : Implémentation initiale
  - Création `flyout-panel.js` + `flyout-panel.css`
  - Création `risk-sidebar.js` + `risk-sidebar.css`
  - Intégration sur `analytics-unified.html`, `rebalance.html`, `execution.html`
  - Restauration du HTML statique dans `risk-dashboard.html`
  - Création page de test `test-flyout-setup.html`

## Références

- [flyout-panel.js](../static/components/flyout-panel.js)
- [risk-sidebar.js](../static/components/risk-sidebar.js)
- [risk-dashboard.html (sidebar statique)](../static/risk-dashboard.html#L2106-L2240)
- [Test Setup](../static/test-flyout-setup.html)
