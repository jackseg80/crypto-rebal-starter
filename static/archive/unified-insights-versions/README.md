# Versions archivées - Unified Insights & Phase Engine

## Fichiers archivés (2025-09-30)

- `unified-insights.js` : Version legacy (avant v2)
- `unified-insights-v2-clean.js` : Tentative simplification (non utilisée)
- `unified-insights-v2-broken.js` : Version cassée (dépendance phase-engine-new.js)
- `phase-engine-new.js` : Version dev (uniquement utilisée par broken)
- `unified-insights-v2-backup.js` : Backup avant refactor

## Versions actives

- **Production** : `static/core/unified-insights-v2.js`
- **Phase Engine** : `static/core/phase-engine.js`

## Références

Ces fichiers ont été archivés car ils n'étaient plus utilisés dans le code de production.
Seule `unified-insights-v2-broken.js` référençait `phase-engine-new.js`, et aucune page
production ne les utilisait.
