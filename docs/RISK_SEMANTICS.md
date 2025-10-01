# Risk Semantics — Source de Vérité

> **⚠️ Règle Canonique — Sémantique Risk**
>
> Le **Risk Score** est un indicateur **positif** de robustesse, borné **[0..100]**.
>
> **Convention** : Plus haut = plus robuste (risque perçu plus faible).
>
> **Conséquence** : Dans le Decision Index (DI), Risk contribue **positivement** :
> ```
> DI = wCycle·scoreCycle + wOnchain·scoreOnchain + wRisk·scoreRisk
> ```
>
> **❌ Interdit** : Ne jamais inverser avec `100 - scoreRisk` (calculs, visualisations, contributions).
>
> **Visualisation** : Contribution = `(poids × score) / Σ(poids × score)`
>
> 📖 **Source de vérité** : [docs/RISK_SEMANTICS.md](RISK_SEMANTICS.md)

## QA Checklist
- Aucun `100 - scoreRisk` dans le code ni dans les docs.
- Contribution Risk cohérente avec son poids configuré.
- Visualisations et agrégations vérifiées côté UI et backend.
