# Développement

## Installation rapide
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

## Conventions
- Style Python conforme au projet (voir existant), lint via ruff si configuré.
- Ne pas introduire de dépendances inutiles.

## Tests et validation
- Si présents, exécuter tests depuis `tests/`.
- Valider endpoints via `/docs`.

## Debug & outils
- Dossier `debug/` pour scripts et pages de test.
- Pages locales utiles: `static/` (rebalance, risk, execution, monitoring).

Historique détaillé: DEVELOPER_GUIDE.md et TEST_INTEGRATION_GUIDE.md sont dépréciés au profit de cette page.


### Règles de développement (cap)

- Utiliser exclusivement `selectCapPercent(state)` pour tout calcul/affichage de cap.
- Si besoin de détails: `selectPolicyCapPercent` (principal) et `selectEngineCapPercent` (secondaire).
- Ne jamais faire confiance à des champs legacy; normaliser les valeurs (0–1 → %).
