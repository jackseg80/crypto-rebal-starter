# Migration Risk Dashboard - Instructions

## Modifications à Appliquer à `risk-dashboard.html`

### 1. Remplacer le bloc CSS inline (lignes 39-1928)

**Avant :**
```html
<style>
  /* ===== Container responsive ===== */
  .container {
    ...
  }
  /* ... ~1900 lignes de CSS ... */
</style>
```

**Après :**
```html
<!-- Risk Dashboard CSS -->
<link rel="stylesheet" href="css/risk-dashboard.css">
```

**Action :** Supprimer tout le bloc `<style>...</style>` (lignes 39-1928) et le remplacer par le `<link>` ci-dessus.

---

### 2. Charger le module orchestrateur (après ligne 1936)

**Avant :**
```html
<script type="module" src="components/tooltips.js"></script>
</head>
```

**Après :**
```html
<script type="module" src="components/tooltips.js"></script>

<!-- Risk Dashboard Orchestrator -->
<script type="module" src="modules/risk-dashboard-main.js"></script>
</head>
```

**Action :** Ajouter l'import du module orchestrateur avant la fermeture du `</head>`.

---

### 3. Retirer la fonction switchTab inline (ligne ~2309)

**Avant :**
```javascript
window.switchTab = function (tabName) {
  console.log(`🔄 Switching to tab: ${tabName}`);
  // ... code inline ...
};
```

**Après :**
```javascript
// switchTab is now handled by modules/risk-dashboard-main.js
// Legacy implementation removed
```

**Action :** Commenter ou supprimer la fonction `window.switchTab` inline (le module orchestrateur la gère maintenant).

---

## Résultat Attendu

**Réduction de taille :**
- **Avant :** ~5000+ lignes dans `risk-dashboard.html`
- **Après :** ~3100 lignes dans `risk-dashboard.html`
- **Externalisé :** ~3000 lignes dans modules séparés

**Fichiers créés :**
1. `css/risk-dashboard.css` (~1900 lignes)
2. `modules/risk-utils.js` (~400 lignes)
3. `modules/risk-dashboard-main.js` (~200 lignes)
4. `modules/alerts-tab.js` (~450 lignes)
5. `modules/risk-overview-tab.js` (stub)
6. `modules/cycles-tab.js` (stub)
7. `modules/targets-tab.js` (stub)

**Mode de fonctionnement :**
- L'orchestrateur (`risk-dashboard-main.js`) gère les onglets
- L'onglet **Alerts** utilise le nouveau module complet
- Les onglets **Risk**, **Cycles**, **Targets** utilisent temporairement le code legacy (stubs)
- Migration progressive : chaque onglet peut être migré indépendamment plus tard

---

## Test Rapide

1. Ouvrir `http://localhost:8000/static/risk-dashboard.html`
2. Vérifier que la page se charge correctement
3. Tester la navigation entre onglets
4. Vérifier que l'onglet **Alerts History** fonctionne avec le nouveau module
5. Vérifier que le refresh fonctionne
6. Vérifier la console pour les logs (`🚀 Rendering...`)

---

## Prochaines Étapes (Optionnel)

Pour finaliser la migration complète :

1. **Migrer Risk Overview** : Déplacer la logique de rendu dans `risk-overview-tab.js`
2. **Migrer Cycles** : Extraire la logique du graphique Bitcoin dans `cycles-tab.js`
3. **Migrer Targets** : Déplacer la logique targets dans `targets-tab.js`
4. **Nettoyer** : Supprimer le code legacy une fois tous les onglets migrés

---

## Commandes Git

```bash
# Ajouter les nouveaux fichiers
git add static/css/risk-dashboard.css
git add static/modules/risk-utils.js
git add static/modules/risk-dashboard-main.js
git add static/modules/alerts-tab.js
git add static/modules/risk-overview-tab.js
git add static/modules/cycles-tab.js
git add static/modules/targets-tab.js

# Commit
git commit -m "refactor(risk-dashboard): extract CSS and modules for better maintainability

- Externalize CSS (~1900 lines) to css/risk-dashboard.css
- Create risk-utils.js with common helpers (~400 lines)
- Create risk-dashboard-main.js orchestrator (~200 lines)
- Migrate Alerts tab to alerts-tab.js (~450 lines)
- Add stubs for Risk/Cycles/Targets tabs (progressive migration)
- Reduce risk-dashboard.html from 5000+ to ~3100 lines

Benefits:
- Better code organization and maintainability
- Easier debugging (separated concerns)
- Better browser caching
- Lazy loading support for tabs
- Easier collaboration (smaller files)"
```
