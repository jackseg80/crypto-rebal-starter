# Market Opportunities - Next Steps & Questions

> **Pour reprendre la discussion efficacement**
> **Date:** 28 octobre 2025
> **Contexte:** Système fonctionnel à 80%, 3 bugs mineurs restants

---

## 📋 Questions Critiques pour l'Utilisateur

### 1. Actions Européennes (Fix Unknown 42%)

**Question:** Quelles actions **européennes/suisses** avez-vous dans votre portfolio de 29 positions ?

**Pourquoi:** 5 symboles causent des erreurs 404 avec Yahoo Finance. Ce sont probablement des actions européennes avec format spécial.

**Exemples attendus:**
- Nestlé → `NESN.SW`
- Roche → `ROG.SW`
- UBS → `UBSG.SW`
- Richemont → `CFR.SW`
- BMW → `BMW.DE`
- LVMH → `MC.PA`

**Action à faire:** Une fois les symboles identifiés, ajouter détection automatique et retry avec suffix approprié (.SW pour Suisse, .PA pour France, .DE pour Allemagne).

---

### 2. Position la Plus Importante (Comprendre Suggested Sales = 0)

**Question:** Quelle est votre **plus grosse position** en % du portfolio ?

**Options:**
- a) < 10% (aucune position dominante)
- b) 10-15% (concentration modérée)
- c) 15-20% (concentration élevée)
- d) > 20% (très concentré)

**Pourquoi:** Le système suggère 0 ventes malgré €52k de besoins. Cela peut indiquer:
- Toutes les positions < 15% (threshold over-concentration)
- Top 3 holdings représentent >80% du portfolio (tous protégés)
- Aucune position avec momentum négatif récent

**Exemple:** Si NVDA = 25% du portfolio, devrait être suggéré en vente (30% de 25% = 7.5% du portfolio = €9,585).

---

### 3. Préférences Suggestions de Vente (Assouplir Critères)

**Question:** Voulez-vous que le système soit **plus agressif** dans les suggestions de vente ?

**Options actuelles (restrictives):**
- Max 30% vente par position
- Top 3 holdings protégés (jamais vendus)
- Seuil over-concentration: 15% du portfolio
- Momentum négatif requis pour trigger vente

**Options proposées (plus souples):**
- a) **Réduire seuil concentration de 15% → 10%** (suggère ventes dès 10% du portfolio)
- b) **Autoriser vente même sans momentum négatif** (si concentration >10%)
- c) **Protéger seulement top 2 holdings** (au lieu de top 3)
- d) **Garder critères actuels** (mais ajouter logs pour comprendre pourquoi 0 ventes)

**Recommandation:** Option (a) + (d) - Réduire à 10% + ajouter logs de debug.

---

## 🐛 Bugs à Corriger (Par Ordre de Priorité)

### Bug #1: Unknown 42% - Actions Européennes Non Détectées

**Symptôme:**
```
Unknown: 42.1% du portfolio
5 x "ERROR yfinance: HTTP Error 404"
```

**Solution:**
1. Identifier les 5 symboles qui échouent (voir logs)
2. Ajouter mapping symboles européens:
   ```python
   # Format Yahoo Finance pour actions européennes
   EUROPEAN_EXCHANGES = {
       'CH': '.SW',  # Suisse (Swiss Exchange)
       'DE': '.DE',  # Allemagne (Xetra)
       'FR': '.PA',  # France (Euronext Paris)
       'UK': '.L',   # UK (London)
   }
   ```
3. Retry avec suffix si 404:
   ```python
   if "HTTP Error 404":
       for suffix in ['.SW', '.PA', '.DE', '.L']:
           ticker = yf.Ticker(f"{symbol}{suffix}")
           if ticker.info.get('sector'):
               return ticker.info['sector']
   ```

**Fichier:** `services/ml/bourse/opportunity_scanner.py` (ligne 219-246)

**Priorité:** 🔴 **CRITIQUE** - 42% du portfolio non classé

---

### Bug #2: Suggested Sales = 0 - Aucune Vente Suggérée

**Symptôme:**
```
Need: €51,934
Suggested sales: 0 (sufficient: False)
```

**Diagnostic nécessaire:**
```python
# Ajouter logs dans portfolio_gap_detector.py
logger.info(f"Protected symbols: {protected_symbols}")
logger.info(f"Positions evaluated: {len(positions)}")
logger.info(f"Positions scored: {len(scored_positions)}")
for pos in scored_positions[:10]:
    logger.info(f"  {pos['symbol']}: score={pos['sale_score']}, sellable={pos['sellable']}, weight={pos.get('weight', 0):.1f}%")
```

**Solution (après diagnostic):**
1. Si toutes positions < 15%: Réduire threshold à 10%
2. Si top 3 = 80%+: Protéger seulement top 2
3. Si aucun momentum négatif: Autoriser vente sur concentration seule

**Fichier:** `services/ml/bourse/portfolio_gap_detector.py` (lignes 40-45, 100-150)

**Priorité:** 🟠 **IMPORTANT** - Feature incomplète

---

### Bug #3: Duplication Secteurs - Mapping Incomplet

**Symptôme:**
```
Before Allocation:
  Consumer Cyclical: 14.5%        ← Yahoo Finance
  Consumer Defensive: 2.9%        ← Yahoo Finance
  Financial Services: 2.0%        ← Yahoo Finance

Target (GICS):
  Consumer Discretionary (≠ Cyclical)
  Consumer Staples (≠ Defensive)
  Financials (≠ Financial Services)
```

**Solution:**
```python
# Dans SECTOR_MAPPING (ligne 67-124), ajouter:
SECTOR_MAPPING = {
    # ... mappings existants ...

    # Yahoo Finance → GICS
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Financial Services": "Financials",
}
```

**Fichier:** `services/ml/bourse/opportunity_scanner.py` (lignes 67-124)

**Priorité:** 🟡 **MINEUR** - Cosmétique, n'empêche pas le fonctionnement

---

## 🎯 Plan d'Action Suggéré

### Session 1: Diagnostic (15 min)

1. **Identifier actions européennes**
   ```powershell
   # Lire logs pour trouver symboles qui échouent
   Get-Content logs\app.log | Select-String "❌|HTTP Error 404" -Context 1
   ```

2. **Analyser poids positions**
   ```powershell
   # Voir allocation actuelle dans dashboard
   # Onglet "Positions" → Trier par "Value" descendant
   ```

3. **Comprendre top 3 holdings**
   ```
   Position 1: SYMBOL (X%)
   Position 2: SYMBOL (Y%)
   Position 3: SYMBOL (Z%)
   Total top 3: (X+Y+Z)%
   ```

### Session 2: Corrections (30-45 min)

1. **Fixer Unknown 42%** (15 min)
   - Implémenter détection symboles européens
   - Tester avec symboles identifiés

2. **Fixer Suggested Sales = 0** (20 min)
   - Ajouter logs debug
   - Scanner à nouveau, analyser logs
   - Ajuster critères selon diagnostic

3. **Fixer duplication secteurs** (5 min)
   - Compléter SECTOR_MAPPING
   - Tester que consolidation fonctionne

### Session 3: Tests & Validation (15 min)

1. **Vérifier Unknown < 5%**
2. **Vérifier Suggested Sales ≥ 1**
3. **Vérifier pas de duplication secteurs**
4. **Performance scan < 10 secondes** (avec cache)

---

## 📊 Métriques de Succès

| Métrique | Actuel | Cible | Status |
|----------|--------|-------|--------|
| **Unknown %** | 42.1% | < 5% | 🔴 |
| **Suggested Sales** | 0 | ≥ 1 | 🔴 |
| **Secteurs dupliqués** | Oui | Non | 🟡 |
| **Capital Needed** | €51,934 | ✅ OK | ✅ |
| **Gaps détectés** | 5 | ✅ OK | ✅ |
| **Scores calculés** | 54-62 | ✅ OK | ✅ |
| **Performance scan** | 19s | < 10s | 🟡 |

---

## 📁 Fichiers à Avoir Sous la Main

### Lecture Obligatoire
- [MARKET_OPPORTUNITIES_SESSION_SUMMARY.md](MARKET_OPPORTUNITIES_SESSION_SUMMARY.md) ← **Lire en premier**
- [MARKET_OPPORTUNITIES_SYSTEM.md](MARKET_OPPORTUNITIES_SYSTEM.md) (section Troubleshooting)

### Modification Probable
- `services/ml/bourse/opportunity_scanner.py` (Bug #1 et #3)
- `services/ml/bourse/portfolio_gap_detector.py` (Bug #2)

### Référence
- `CLAUDE.md` (section Features Avancées)
- `logs/app.log` (derniers 200 lignes)

---

## 🔧 Commandes Utiles

### Redémarrer serveur (TOUJOURS après modif Python)
```powershell
# Ctrl+C pour arrêter
.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --port 8000
```

### Voir logs en temps réel
```powershell
Get-Content logs\app.log -Wait -Tail 30
```

### Chercher symboles avec erreur
```powershell
Get-Content logs\app.log | Select-String "❌|HTTP Error 404" -Context 2 | Select-Object -Last 10
```

### Voir allocation actuelle
```powershell
Get-Content logs\app.log | Select-String "Current allocation|sector_values" | Select-Object -Last 5
```

---

## 💡 Contexte Additionnel

### Pourquoi CSV Saxo n'a pas de secteurs ?

Le CSV exporté de Saxo Bank contient:
```
Instruments, Quantité, Prix entrée, Valeur actuelle (EUR), Symbole, ISIN, Type d'actif
```

**Pas de colonne "Secteur" ou "Industry"** → Solution: Enrichissement automatique via Yahoo Finance.

### Pourquoi Yahoo Finance échoue sur actions européennes ?

Yahoo Finance utilise des **suffixes par exchange**:
- US: Pas de suffix (AAPL, MSFT)
- Suisse: .SW (NESN.SW, ROG.SW)
- France: .PA (MC.PA, OR.PA)
- Allemagne: .DE (BMW.DE, SAP.DE)
- UK: .L (BP.L, HSBA.L)

Notre code actuel essaie seulement `SYMBOL` sans suffix → 404 pour actions européennes.

### Pourquoi Suggested Sales = 0 ?

**Critères actuels très restrictifs:**
1. Top 3 holdings **jamais vendus** (protection)
2. Vente seulement si position > 15% du portfolio (over-concentration)
3. Vente seulement si momentum négatif 3M

**Si portfolio bien distribué** (ex: 29 positions × 3.4% chacune):
- Aucune position > 15% → Critère 2 jamais satisfait
- Top 3 = 10% du portfolio → Représente peu
- → 0 ventes suggérées malgré besoins

**Solution:** Assouplir critères (10% au lieu de 15%, ou autoriser vente sans momentum négatif).

---

*Document généré pour reprise de session*
*Utilisateur: jack | Portfolio: $127,822 | Status: 🟡 Fonctionnel à 80%*
