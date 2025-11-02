# Module Patrimoine - Documentation

> **Version:** 1.0 (Nov 2025)
> **Status:** ✅ Production Ready

## Vue d'ensemble

Le module **Patrimoine** unifie la gestion de tous les actifs et passifs personnels au-delà des cryptomonnaies et actions. Il remplace et étend l'ancien module "Banks" avec une architecture flexible permettant de tracker :

- **Liquidités** : Comptes bancaires, néobanques, cash
- **Biens Réels** : Immobilier, véhicules, métaux précieux
- **Passifs** : Prêts immobiliers, prêts personnels, cartes de crédit
- **Assurances** : Assurances-vie, assurances investment

## Architecture

### Backend

**Modèles Pydantic** ([models/wealth.py](../models/wealth.py:118-162))
```python
class PatrimoineItemInput(BaseModel):
    name: str                    # Ex: "Maison Lyon 120m²"
    category: Literal[...]       # liquidity | tangible | liability | insurance
    type: Literal[...]          # bank_account | real_estate | mortgage | ...
    value: float                 # Valeur (positif pour actifs, négatif pour passifs)
    currency: str                # CHF | EUR | USD | GBP
    acquisition_date: Optional[str]
    notes: Optional[str]
    metadata: Optional[dict]     # Champs spécifiques par type (JSON flexible)

class PatrimoineItemOutput(WealthBaseModel):
    # Tous les champs de Input +
    id: str                      # UUID généré
    value_usd: Optional[float]   # Conversion USD automatique
```

**Service CRUD** ([services/wealth/patrimoine_service.py](../services/wealth/patrimoine_service.py))
- `list_items(user_id, category=None, type=None)` - Liste avec filtres
- `get_item(user_id, item_id)` - Récupération par ID
- `create_item(user_id, item)` - Création
- `update_item(user_id, item_id, item)` - Mise à jour
- `delete_item(user_id, item_id)` - Suppression
- `get_summary(user_id)` - Net Worth + breakdown par catégorie

**Migration Service** ([services/wealth/patrimoine_migration.py](../services/wealth/patrimoine_migration.py))
- Migration automatique `banks/snapshot.json` → `wealth/patrimoine.json`
- Préserve l'ancien fichier (lecture seule)
- Transforme : `bank_account` → `category=liquidity, type=bank_account`

**API Endpoints** ([api/wealth_endpoints.py](../api/wealth_endpoints.py:49-194))
```
GET    /api/wealth/patrimoine/items          # Liste items (filtres category/type)
GET    /api/wealth/patrimoine/items/{id}     # Récupération item
POST   /api/wealth/patrimoine/items          # Création
PUT    /api/wealth/patrimoine/items/{id}     # Mise à jour
DELETE /api/wealth/patrimoine/items/{id}     # Suppression
GET    /api/wealth/patrimoine/summary        # Net Worth summary
```

**Rétrocompatibilité** ([api/wealth_endpoints.py](../api/wealth_endpoints.py:197-387))
```
GET    /api/wealth/banks/accounts    # Redirige vers patrimoine (filtre bank_account)
POST   /api/wealth/banks/accounts    # Convertit BankAccountInput → PatrimoineItem
PUT    /api/wealth/banks/accounts/{id}
DELETE /api/wealth/banks/accounts/{id}
```

### Frontend

**Dashboard Principal** ([static/wealth-dashboard.html](../static/wealth-dashboard.html))

Structure :
```
┌─────────────────────────────────────┐
│  Net Worth Dashboard                │
│  • Net Worth: $XXX,XXX              │
│  • Total Actifs / Passifs           │
│  • Breakdown par catégorie          │
└─────────────────────────────────────┘

┌──────────┬──────────┬─────────┬──────────┐
│Liquidités│Biens Réels│ Passifs │Assurances│ ← Onglets
└──────────┴──────────┴─────────┴──────────┘
```

**Features UI :**
- ✅ Système d'onglets responsive
- ✅ Tables par type d'asset (bank accounts, real estate, mortgages, etc.)
- ✅ Modal CRUD avec champs dynamiques selon le type
- ✅ Conversion USD automatique
- ✅ Multi-user isolation (localStorage activeUser)
- ✅ Design full-width responsive

**Navigation** ([static/components/nav.js](../static/components/nav.js:219))
- Menu principal : "Banque" → "Patrimoine"
- Lien : `wealth-dashboard.html`

**Redirection** ([static/banks-manager.html](../static/banks-manager.html), [static/banks-dashboard.html](../static/banks-dashboard.html))
- Anciens fichiers convertis en redirection automatique
- Redirigent vers `wealth-dashboard.html?tab=liquidity`

**Dashboard Principal** ([static/dashboard.html](../static/dashboard.html:586-630))
- Tuile "Patrimoine" dans le dashboard principal (Niveau 1)
- Affiche : Net Worth, Actifs/Passifs, Items count
- Graphique doughnut chart avec breakdown par catégorie
- Bouton Export Lists

**Global Overview** ([api/wealth_endpoints.py](../api/wealth_endpoints.py:544-652))
- Intégration dans `/api/wealth/global/summary`
- Affiche le **Net Worth** (actifs - passifs) dans le breakdown global
- Cohérent avec modules Crypto et Bourse

## Données

### Storage Multi-Tenant

**Structure fichiers :**
```
data/users/{user_id}/
  banks/
    snapshot.json           # LEGACY (lecture seule, migration auto)
  wealth/
    patrimoine.json         # NOUVEAU (format unifié)
```

**Format patrimoine.json :**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Maison Lyon 120m²",
      "category": "tangible",
      "type": "real_estate",
      "value": 450000.0,
      "currency": "EUR",
      "acquisition_date": "2020-01-15",
      "notes": "Résidence principale",
      "metadata": {
        "address": "123 rue de Lyon",
        "surface": 120,
        "monthly_payment": 1200,
        "remaining_loan": 200000
      }
    }
  ]
}
```

### Catégories & Types

**4 Catégories principales :**

1. **liquidity** (Liquidités)
   - `bank_account` - Compte bancaire
   - `neobank` - Néobanque (Revolut, N26, etc.)
   - `cash` - Espèces

2. **tangible** (Biens Réels)
   - `real_estate` - Immobilier
   - `vehicle` - Véhicule
   - `precious_metals` - Métaux précieux

3. **liability** (Passifs - valeurs négatives)
   - `mortgage` - Prêt immobilier
   - `loan` - Prêt personnel
   - `credit_card` - Carte de crédit

4. **insurance** (Assurances)
   - `life_insurance` - Assurance-vie
   - `investment_insurance` - Assurance investment

### Champs Metadata Spécifiques

**bank_account :**
```json
{
  "bank_name": "UBS",
  "account_type": "current|savings|pel|livret_a|other"
}
```

**real_estate :**
```json
{
  "address": "123 rue de Lyon",
  "surface": 120,
  "monthly_payment": 1200,
  "remaining_loan": 200000
}
```

**vehicle :**
```json
{
  "brand": "Tesla",
  "model": "Model 3",
  "year": 2023
}
```

**mortgage / loan :**
```json
{
  "monthly_payment": 1200,
  "remaining_months": 180
}
```

## Usage

### Backend

**Créer un item :**
```python
from services.wealth.patrimoine_service import create_item
from models.wealth import PatrimoineItemInput

item = PatrimoineItemInput(
    name="Maison Lyon",
    category="tangible",
    type="real_estate",
    value=450000.0,
    currency="EUR",
    metadata={"surface": 120, "address": "Lyon"}
)

created = create_item(user_id="jack", item=item)
print(f"Created: {created.id} - ${created.value_usd}")
```

**Récupérer le Net Worth :**
```python
from services.wealth.patrimoine_service import get_summary

summary = get_summary(user_id="jack")
print(f"Net Worth: ${summary['net_worth']:.2f}")
print(f"Actifs: ${summary['total_assets']:.2f}")
print(f"Passifs: ${summary['total_liabilities']:.2f}")
```

### Frontend

**Charger les données :**
```javascript
const activeUser = localStorage.getItem('activeUser') || 'demo';

// Summary
const summaryRes = await fetch('/api/wealth/patrimoine/summary', {
    headers: { 'X-User': activeUser }
});
const summary = await summaryRes.json();

// Items
const itemsRes = await fetch('/api/wealth/patrimoine/items', {
    headers: { 'X-User': activeUser }
});
const items = await itemsRes.json();
```

**Créer un item :**
```javascript
const payload = {
    name: "Revolut",
    category: "liquidity",
    type: "neobank",
    value: 5000.0,
    currency: "EUR",
    notes: "Neobank travel"
};

const response = await fetch('/api/wealth/patrimoine/items', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-User': activeUser
    },
    body: JSON.stringify(payload)
});
```

## Migration

### Migration Automatique

La migration se déclenche automatiquement au premier accès pour chaque utilisateur.

**Commande manuelle (Python) :**
```python
from services.wealth.patrimoine_migration import migrate_user_data, migrate_all_users

# Un utilisateur
result = migrate_user_data("jack", force=False)

# Tous les utilisateurs
results = migrate_all_users(force=False)
```

**Transformation :**
```
AVANT (banks/snapshot.json):
{
  "accounts": [
    {
      "id": "uuid",
      "bank_name": "UBS",
      "account_type": "current",
      "balance": 5000.0,
      "currency": "CHF"
    }
  ]
}

APRÈS (wealth/patrimoine.json):
{
  "items": [
    {
      "id": "uuid",
      "name": "UBS (current)",
      "category": "liquidity",
      "type": "bank_account",
      "value": 5000.0,
      "currency": "CHF",
      "metadata": {
        "bank_name": "UBS",
        "account_type": "current"
      }
    }
  ]
}
```

## Tests

**Tests unitaires** ([test_patrimoine_phase1.py](../test_patrimoine_phase1.py))

```bash
# Exécuter tous les tests
.venv/Scripts/python.exe test_patrimoine_phase1.py

# Tests couverts :
# 1. Migration banks.json → patrimoine.json
# 2. List items avec filtres
# 3. Create item (neobank)
# 4. Summary (Net Worth calculation)
# 5. Multi-user isolation
# 6. Migration all users
```

**Tests API manuels :**
```bash
# Summary
curl -H "X-User: jack" http://localhost:8080/api/wealth/patrimoine/summary

# Liste items
curl -H "X-User: jack" http://localhost:8080/api/wealth/patrimoine/items

# Créer immobilier
curl -X POST http://localhost:8080/api/wealth/patrimoine/items \
  -H "X-User: jack" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Maison Lyon",
    "category": "tangible",
    "type": "real_estate",
    "value": 450000.0,
    "currency": "EUR",
    "metadata": {"surface": 120}
  }'
```

## Évolutions Futures

**Phase 3 - Analytics (optionnel) :**
- [ ] Graph évolution Net Worth (historique 30j, 1an)
- [ ] Pie chart répartition actifs par catégorie
- [ ] Trend analysis (patrimoine croissant/décroissant)

**Phase 4 - Features Avancées :**
- [ ] Photos/attachments pour biens immobiliers
- [ ] Historique de valeurs (track modifications)
- [ ] Export CSV/PDF/Excel
- [ ] Alertes sur échéances prêts
- [ ] Calcul ROI immobilier

## Références

**Code :**
- Backend : [services/wealth/](../services/wealth/)
- Frontend : [static/wealth-dashboard.html](../static/wealth-dashboard.html)
- API : [api/wealth_endpoints.py](../api/wealth_endpoints.py)
- Tests : [test_patrimoine_phase1.py](../test_patrimoine_phase1.py)

**Docs Connexes :**
- [CLAUDE.md](../CLAUDE.md) - Guide agent principal
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture globale
- [TODO_WEALTH_MERGE.md](TODO_WEALTH_MERGE.md) - Context wealth namespace

---

**Contributeurs :** Claude Code (Nov 2025)
**Maintenance :** Module production-ready, aucune maintenance critique requise
