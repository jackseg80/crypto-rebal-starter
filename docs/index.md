# Documentation Portal

Bienvenue. Cette documentation est organisée par sujets avec des pages dédiées et un README allégé.

- Quickstart: `docs/quickstart.md`
- Configuration: `docs/configuration.md`
- Guide Utilisateur: `docs/user-guide.md`
- API: `docs/api.md`
- Architecture: `docs/architecture.md`
- Navigation: `docs/navigation.md`
- Governance & Caps: `docs/governance.md`
- Risk Dashboard: `docs/risk-dashboard.md`
- Télémétrie: `docs/telemetry.md`
- Runbooks: `docs/runbooks.md`
- Intégrations (CoinTracking, Kraken, FRED): `docs/integrations.md`
- Développement: `docs/developer.md`
- Dépannage: `docs/troubleshooting.md`
- Refactoring (migration): `docs/refactoring.md`
- Changelog: `CHANGELOG.md`

## Concepts clés

### Sémantique de Risk (Pilier du Decision Index)

**Risk** est un score de robustesse/qualité du risque, borné **[0..100]**.

**Convention** : **Plus haut = mieux** (portefeuille plus robuste / risque perçu plus faible).

**Conséquence** : Dans le calcul du Decision Index (DI), Risk est additionnel (pas de transformation `100 - risk`).

**Formule DI** :
```
DI = wCycle × scoreCycle + wOnchain × scoreOnchain + wRisk × scoreRisk
```

**Visualisation** (barre empilée) : Contribution relative par pilier = `(poids × score) / Σ(poids × score)`.

⚠️ **Ne jamais inverser Risk** (pas de `100 - scoreRisk`) : cela fausserait le DI et les visualisations de contributions.

Archive détaillée (ancienne doc): `docs/_legacy/`

Notes:
- La référence API officielle provient de l’OpenAPI de l’app: `/docs` et `/openapi.json`.
- Les anciens fichiers détaillés restent disponibles pour historique mais sont dépréciés.

### Cap d’exécution (UI)

Pour l’affichage et les simulations:
- `selectCapPercent(state)` fournit le cap en % (policy prioritaire).
- Convergence: `ceil(maxDelta / (capPct/100))`.
