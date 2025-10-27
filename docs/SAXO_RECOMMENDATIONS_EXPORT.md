# Saxo Recommendations Export System

> **AI-friendly text export for portfolio recommendations**
> Last updated: Oct 2025

## 🎯 Overview

Système d'export des recommandations de portfolio (BUY/HOLD/SELL) en format texte structuré (Markdown), optimisé pour analyse par IA (ChatGPT, Claude, etc.) ou archivage.

**Fonctionnalités principales :**
- ✅ Export de 3 horizons temporels en un seul fichier
- ✅ Format Markdown structuré et lisible
- ✅ Métadonnées contextuelles (date, user, portfolio)
- ✅ Statistiques de résumé par timeframe
- ✅ Table complète des recommandations

---

## 📁 Localisation

### Frontend
- **Page** : `static/saxo-dashboard.html` → Onglet "Recommendations"
- **Bouton** : "📄 Export Text (All Timeframes)" dans le header du tableau

### Backend (API)
- **Endpoint** : `GET /api/ml/bourse/portfolio-recommendations`
- **Paramètres** :
  - `user_id` : Utilisateur actif
  - `timeframe` : `short` | `medium` | `long`
  - `lookback_days` : Jours d'historique (défaut: 90)
  - `file_key` : Fichier CSV Saxo spécifique (optionnel)
  - `cash_amount` : Liquidités disponibles (optionnel)

---

## 🔧 Fonctionnement

### 1. Horizons temporels exportés

L'export génère des recommandations pour **3 timeframes** :

| Timeframe | Horizon | Description | Focus |
|-----------|---------|-------------|-------|
| **SHORT** | 1-2 Weeks | Trading | Signaux techniques court terme |
| **MEDIUM** | 1 Month | Tactical | Équilibre technique + fondamentaux |
| **LONG** | 3-6 Months | Strategic | Fondamentaux et tendances macro |

**Note** : L'algorithme ajuste les recommandations selon l'horizon :
- Court terme → Plus de poids sur RSI, MACD
- Long terme → Plus de Strong Buy/Sell basés sur fondamentaux

### 2. Processus d'export

```javascript
// Frontend: saxo-dashboard.html (lignes 4520-4642)
async function exportRecommendationsToText() {
    // 1. Fetch data pour les 3 timeframes
    for (const tf of ['short', 'medium', 'long']) {
        const response = await fetch(`/api/ml/bourse/portfolio-recommendations?timeframe=${tf}&...`);
        const data = await response.json();

        // 2. Génère section Markdown
        markdownText += formatTimeframeSection(tf, data);
    }

    // 3. Télécharge fichier .txt
    downloadFile(markdownText, `portfolio-recommendations-${date}.txt`);
}
```

**Requêtes API** : 3 appels séquentiels (un par timeframe)
**Temps** : ~2-5 secondes selon taille portfolio
**Output** : Fichier `.txt` avec Markdown

---

## 📄 Format du fichier exporté

### Structure générale

```markdown
# Portfolio Recommendations Export

**Generated:** DD/MM/YYYY HH:MM:SS
**User:** jack
**Portfolio:** filename.csv

---

## SHORT TERM (1-2 Weeks) - Trading Horizon

### Market Context
- **Cycle Score:** 65/100
- **Market Regime:** Expansion
- **Risk Level:** Medium
- **ML Sentiment:** Neutral

### Summary Statistics
- **Total Positions:** 36
- **Strong Buy:** 2
- **Buy:** 10
- **Hold:** 18
- **Sell:** 6
- **Strong Sell:** 0

### Recommendations

| Symbol | Name | Action | Target | Stop Loss | R/R | Confidence | Rationale |
|--------|------|--------|--------|-----------|-----|------------|----------|
| BRKb | BRKb | STRONG BUY | N/A | N/A | N/A | 96% | ⚠️ Technical: RSI 91... |
| AAPL | AAPL | HOLD | N/A | N/A | N/A | 97% | ⚠️ Technical: RSI 57... |

---

## MEDIUM TERM (1 Month) - Tactical Horizon
[...]

## LONG TERM (3-6 Months) - Strategic Horizon
[...]

## Notes
[Explications des métriques]
```

### Colonnes du tableau

| Colonne | Description | Valeurs possibles |
|---------|-------------|-------------------|
| **Symbol** | Ticker du titre | AAPL, MSFT, ROG, etc. |
| **Name** | Nom (tronqué 20 chars) | "Apple Inc", "Roche", etc. |
| **Action** | Recommandation | STRONG BUY, BUY, HOLD, SELL, STRONG SELL |
| **Target** | Prix cible | Prix USD ou N/A |
| **Stop Loss** | Stop loss | Prix USD ou N/A |
| **R/R** | Risk/Reward Ratio | Ratio ou N/A |
| **Confidence** | Confiance ML | 70%-100% |
| **Rationale** | Justification (50 chars) | Analyse technique/fondamentale |

### Données actuellement disponibles

**✅ Données exportées :**
- Symbol, Name, Action, Confidence ✅
- Rationale (tronqué à 50 caractères) ✅
- Summary Statistics (counts par action) ✅

**⚠️ Données actuellement "N/A" :**
- Market Context (Cycle Score, Regime, Risk Level, ML Sentiment) ❌
- Target Price ❌
- Stop Loss ❌
- Risk/Reward Ratio ❌

**Raison** : Ces métriques ne sont pas retournées par l'endpoint API actuellement. L'algorithme se concentre sur la classification (BUY/HOLD/SELL) et la confidence.

---

## 🤖 Optimisé pour analyse IA

### Pourquoi ce format ?

**Markdown structuré** :
- ✅ Sections hiérarchiques (`##`, `###`) faciles à parser
- ✅ Tables bien formattées (`|` séparateurs)
- ✅ Métadonnées en début de fichier
- ✅ Notes explicatives en fin de fichier

**Cas d'usage IA** :
1. **Upload dans ChatGPT/Claude** :
   ```
   "Analyse ces recommandations et identifie les meilleures opportunités"
   "Compare les signaux court terme vs long terme"
   "Quels titres sont cohérents sur les 3 timeframes ?"
   ```

2. **Analyse programmatique** :
   ```python
   import re

   # Parser le fichier Markdown
   with open('portfolio-recommendations-2025-10-27.txt') as f:
       content = f.read()

   # Extraire tableaux avec regex
   tables = re.findall(r'\| Symbol \|.*?\n\n', content, re.DOTALL)

   # Analyser les Strong Buy
   strong_buys = [line for line in tables if 'STRONG BUY' in line]
   ```

3. **Archivage et comparaison** :
   - Comparer recommandations semaine N vs semaine N-1
   - Identifier changements de signaux
   - Tracker performance historique

---

## 📊 Cas d'usage

### 1. Sélection de titres (Portfolio Screening)

**Possible ✅ avec données actuelles :**
- Identifier Strong Buy sur multiple timeframes
- Prioriser par Confidence (95%+ = haute confiance)
- Voir évolution des recommandations (court → moyen → long)

**Exemple d'analyse** :
```
BRKb (Berkshire Hathaway):
  - Short: STRONG BUY (92%)
  - Medium: STRONG BUY (96%)
  - Long: STRONG BUY (96%)
→ Signal très fort et cohérent = priorité haute

TSLA (Tesla):
  - Short: HOLD (97%)
  - Medium: HOLD (97%)
  - Long: SELL (97%)
→ Divergence = prudence, tenir court terme puis sortir
```

### 2. Consensus multi-timeframe

**Analyse des patterns** :
- Titres avec même action sur 3 timeframes → Forte conviction
- Titres avec divergence → Signal mixed, attendre confirmation
- Migration BUY → HOLD → SELL → Tendance baissière

**Exemple (extrait réel)** :
```
ROG (Roche):
  - Short: BUY (97%)
  - Medium: STRONG BUY (97%)
  - Long: STRONG BUY (96%)
→ Conviction croissante = excellent signal
```

### 3. Limitations actuelles

**Impossible ❌ sans Target/Stop/R/R :**
- Calcul de position sizing optimal
- Gestion du risque (où placer stop ?)
- Estimation du potentiel (combien gagner ?)
- Comparaison risque/rendement entre titres

**Workaround** :
- Utiliser les signaux pour sélection de titres
- Compléter manuellement avec analyse technique pour stops/targets
- Ou attendre que l'API retourne ces métriques

---

## 🧪 Exemples de résultats

### Distribution des actions par timeframe

| Timeframe | Strong Buy | Buy | Hold | Sell | Strong Sell |
|-----------|------------|-----|------|------|-------------|
| **Short (1-2 weeks)** | 2 | 10 | 18 | 6 | 0 |
| **Medium (1 month)** | 5 | 8 | 17 | 6 | 0 |
| **Long (3-6 months)** | 9 | 5 | 16 | 6 | 0 |

**Observation** : Plus long l'horizon, plus de Strong Buy (focus sur fondamentaux)

### Top signaux consistants

**Strong Buy sur les 3 timeframes** :
- BRKb (Berkshire) : 96% confidence
- ROG (Roche) : 96-97% confidence
- UHRN (Swatch) : 92-93% confidence

**Hold consistant** :
- AMD (8 positions dupliquées) : 88% confidence
- AAPL, GOOGL, COIN : 95-97% confidence

---

## 🔧 Implémentation technique

### Frontend (saxo-dashboard.html)

**Bouton d'export (ligne 793)** :
```html
<button id="btnExportTextRecs" class="btn secondary small">
    📄 Export Text (All Timeframes)
</button>
```

**Fonction principale (lignes 4520-4642)** :
```javascript
async function exportRecommendationsToText() {
    // 1. Fetch 3 timeframes
    for (const tf of ['short', 'medium', 'long']) {
        const url = `/api/ml/bourse/portfolio-recommendations?timeframe=${tf}&...`;
        const data = await fetch(url).then(r => r.json());

        // 2. Build Markdown sections
        markdownText += buildTimeframeSection(tf, data);
    }

    // 3. Download as .txt file
    downloadAsTextFile(markdownText, `portfolio-recommendations-${date}.txt`);
}
```

**Gestion du rationale (lignes 4598-4609)** :
```javascript
// Handle rationale (could be string, array, or object)
let rationale = 'N/A';
if (rec.rationale) {
    if (typeof rec.rationale === 'string') {
        rationale = rec.rationale.replace(/\n/g, ' ').substring(0, 50);
    } else if (Array.isArray(rec.rationale)) {
        rationale = rec.rationale.join('; ').substring(0, 50);
    } else {
        rationale = String(rec.rationale).substring(0, 50);
    }
    if (rationale.length >= 50) rationale += '...';
}
```

**États du bouton** :
1. Normal : "📄 Export Text (All Timeframes)"
2. Loading : "⏳ Generating..." (disabled)
3. Success : "✅ Downloaded!" (2 secondes, puis reset)
4. Error : Alert + reset

---

## 🐛 Troubleshooting

### Erreur : "Failed to fetch recommendations"

**Cause** : API endpoint ne répond pas ou erreur serveur

**Solution** :
1. Vérifier que le serveur backend tourne (`http://localhost:8000`)
2. Vérifier les logs backend pour erreurs API
3. Tester l'endpoint manuellement :
   ```bash
   curl "http://localhost:8000/api/ml/bourse/portfolio-recommendations?user_id=jack&timeframe=short"
   ```

### Erreur : "TypeError: rec.rationale.replace is not a function"

**Cause** : `rationale` n'est pas une string (array ou objet)

**Solution** : ✅ Déjà corrigé (commit `2028df6`)
- Le code gère maintenant string, array, et objects

### Export vide ou données manquantes

**Cause** : Aucune recommandation générée pour le portfolio

**Vérifications** :
1. CSV Saxo chargé correctement ?
2. Positions valides dans le portfolio ?
3. API ML fonctionnelle ?

---

## 📚 Références

### Code
- Frontend : [static/saxo-dashboard.html:4520-4642](../static/saxo-dashboard.html#L4520-L4642)
- API Endpoint : [api/ml_endpoints.py](../api/ml_endpoints.py) (endpoint `portfolio-recommendations`)

### Docs connexes
- Multi-Currency Support : [MULTI_CURRENCY_IMPLEMENTATION.md](MULTI_CURRENCY_IMPLEMENTATION.md)
- FX System : [FX_SYSTEM.md](FX_SYSTEM.md)
- Stop Loss System : [STOP_LOSS_SYSTEM.md](STOP_LOSS_SYSTEM.md)

### Commits
- `ccd9bf1` - feat(saxo): add AI-friendly text export for recommendations
- `2028df6` - fix(saxo): handle non-string rationale in recommendations export

---

## 🔮 Améliorations futures

### P1 - Court terme
- [ ] Ajouter Target Price, Stop Loss, R/R au fichier (si API retourne)
- [ ] Ajouter Market Context (Cycle Score, Regime, etc.)
- [ ] Bouton "Copy to Clipboard" pour upload rapide dans ChatGPT
- [ ] Export en CSV en plus du Markdown

### P2 - Moyen terme
- [ ] Export filtré (seulement Strong Buy/Buy)
- [ ] Comparaison automatique entre 2 exports (diff)
- [ ] Génération automatique de résumé par IA
- [ ] Historique des exports (archivage automatique)

### P3 - Long terme
- [ ] API dédiée `/api/exports/recommendations/text`
- [ ] Scheduled exports (hebdomadaires automatiques)
- [ ] Email delivery des exports
- [ ] Dashboard de suivi des recommandations dans le temps

---

*Système d'export des recommandations Saxo - Format optimisé pour analyse IA*
