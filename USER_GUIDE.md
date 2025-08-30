# User Guide - Crypto Rebalancer

## 🎯 Bienvenue !

Ce guide vous accompagne dans l'utilisation complète du Crypto Rebalancer, une plateforme professionnelle de gestion et rebalancement de portfolios crypto. Que vous soyez débutant ou expert, vous trouverez ici tout ce qu'il faut savoir pour optimiser votre portfolio.

## 📋 Table des matières

- [Installation & Configuration](#-installation--configuration)
- [Interface Générale](#-interface-générale)
- [Configuration Initiale](#-configuration-initiale)
- [Dashboard Portfolio](#-dashboard-portfolio)
- [Rebalancement Intelligent](#-rebalancement-intelligent)
- [Gestion des Risques](#-gestion-des-risques)
- [Trading & Exécution](#-trading--exécution)
- [Analytics Avancées](#-analytics-avancées)
- [Surveillance & Monitoring](#-surveillance--monitoring)
- [Workflows Recommandés](#-workflows-recommandés)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Installation & Configuration

### Prérequis

- **Python 3.9+** installé sur votre système
- **Compte CoinTracking** (recommandé) avec API activée
- **Navigateur web moderne** (Chrome, Firefox, Safari, Edge)

### Installation Rapide

```bash
# 1. Téléchargement
git clone https://github.com/votre-org/crypto-rebal-starter.git
cd crypto-rebal-starter

# 2. Installation des dépendances
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
# Éditez le fichier .env avec vos clés API

# 4. Lancement
uvicorn api.main:app --reload --port 8000
```

### Première Vérification

1. **Ouvrir le navigateur** : `http://127.0.0.1:8000/docs`
2. **Tester l'API** : Cliquer sur `/healthz` puis "Try it out" → "Execute"
3. **Résultat attendu** : `{"status": "ok", "timestamp": "..."}`

---

## 🖥️ Interface Générale

### Navigation Bi-Sectionnelle

L'interface est organisée en deux sections principales :

#### 📊 **Analytics & Decisions** (Interface Business)
- **🏠 Dashboard** : Vue d'ensemble de votre portfolio
- **🛡️ Risk Dashboard** : Analyse de risque institutionnelle  
- **⚖️ Rebalance** : Génération de plans de rebalancement
- **🏷️ Aliases** : Gestion des classifications crypto
- **⚙️ Settings** : Configuration centralisée

#### 🚀 **Execution & Diagnostics** (Interface Technique)
- **🚀 Execute** : Dashboard d'exécution temps réel
- **📈 History** : Historique et analytics des trades
- **🔍 Monitor** : Surveillance des connexions avancée

### Système de Thème

- **Mode Light/Dark** : Bouton de bascule en haut à droite
- **Persistance** : Votre préférence est sauvegardée automatiquement
- **Cohérence** : Le thème s'applique à toutes les interfaces

---

## ⚙️ Configuration Initiale

### 1. Page Settings (Point de Départ Obligatoire)

**🎯 Commencez TOUJOURS par Settings !**

Naviguez vers `static/settings.html` ou cliquez sur **⚙️ Settings**.

#### Configuration des Sources de Données

**Option 1 : CoinTracking CSV (Recommandé)**
- Source la plus fiable et rapide
- Exportez depuis CoinTracking : `Balance by Exchange`
- Placez le fichier dans `data/raw/`
- L'application le détecte automatiquement

**Option 2 : CoinTracking API**
- Plus pratique mais parfois moins stable
- Nécessite vos clés API CoinTracking
- Saisie sécurisée avec masquage des champs

**Option 3 : Mode Démo**
- Données simulées pour tester l'interface
- Parfait pour découvrir les fonctionnalités

#### Configuration du Pricing

**🚀 Hybride (Recommandé)**
- Combine vitesse et précision
- Prix locaux + basculement automatique vers marché si données anciennes
- Optimal pour usage quotidien

**🏠 Local**
- Le plus rapide (calcul depuis vos balances)
- Idéal si vos données CoinTracking sont très récentes

**⚡ Auto/Marché** 
- Le plus précis (prix temps réel)
- Plus lent mais données exactes du marché

### 2. Configuration des Clés API

#### CoinTracking API
```
API Key    : [Votre clé de 32 caractères]
API Secret : [Votre secret de 64 caractères]
```

**Comment obtenir vos clés :**
1. Connectez-vous à CoinTracking.info
2. Allez dans `Settings` → `API`
3. Créez une nouvelle clé avec permissions `Read`
4. Copiez/collez dans l'interface Settings

#### CoinGecko API (Optionnel)
```
API Key : [Votre clé Pro CoinGecko]
```

Améliore la fiabilité des prix et métadonnées crypto.

### 3. Validation de Configuration

Après saisie, l'interface affiche :
- ✅ **Clés valides** : Configuration réussie
- ❌ **Erreur** : Vérifiez vos clés ou la connexion internet
- **Indicateurs** : Source active et mode pricing en bas de page

---

## 🏠 Dashboard Portfolio

### Vue d'Ensemble

Le Dashboard (`static/dashboard.html`) offre une vue complète de votre portfolio avec analytics avancées.

#### Métriques Principales

**Valeur & Composition**
- **Valeur Totale** : Valeur USD actualisée
- **Nombre d'Assets** : Cryptos détenues
- **Score de Diversification** : Indice de répartition (0-100)
- **Top 5 Concentration** : % des 5 plus gros holdings

**Indicateurs de Risque**
- **Risk Score** : Score composite de risque (0-100)
- **Volatilité 30J** : Volatilité récente du portfolio  
- **Max Drawdown** : Plus grosse perte historique

### Graphiques Interactifs

#### 1. **Distribution par Groupes**
- **Chart en Donut** : Répartition visuelle par catégories crypto
- **Groupes Intelligents** : BTC, ETH, Stablecoins, SOL, L1/L0, L2, DeFi, AI/Data, Gaming, Memes, Others
- **Valeurs Cliquables** : Détail au survol avec montants USD

#### 2. **Performance Temporelle**  
- **Graphique en Ligne** : Évolution de la valeur portfolio
- **Benchmarks** : Comparaison avec BTC, ETH, et indices
- **Périodes** : 7J, 30J, 90J, 1An

#### 3. **Analyse de Corrélation**
- **Heatmap** : Corrélations entre vos principaux assets
- **Diversification** : Identification des positions redondantes
- **Risk Clustering** : Regroupements par comportement de prix

### Recommandations Intelligentes

Le système analyse votre portfolio et propose :

**Exemples de Recommandations**
- 📉 "Réduisez la concentration BTC (actuellement 45%)"
- 📈 "Augmentez l'allocation stablecoins pour plus de stabilité"  
- ⚖️ "Portfolio bien diversifié, continuez cette stratégie"
- 🔄 "Un rebalancement améliorerait le ratio risque/rendement"

---

## ⚖️ Rebalancement Intelligent

### Concept de Base

Le rebalancement optimise votre allocation pour maintenir vos cibles d'investissement tout en tenant compte des coûts de transaction et de la localisation des assets.

### Interface Rebalance

Accédez à `static/rebalance.html` ou cliquez sur **⚖️ Rebalance**.

#### 1. **Définition des Cibles**

**Mode Manuel (Standard)**
```
BTC: 35%          # Bitcoin et wrapped variants
ETH: 25%          # Ethereum et liquid staking  
Stablecoins: 15%  # USDT, USDC, DAI, etc.
SOL: 10%          # Solana ecosystem
L1/L0 majors: 10% # Autres Layer 1
Others: 5%        # Reste du portfolio
```

**Mode Dynamique (Avancé)**
- Cibles ajustées automatiquement selon les cycles crypto
- Intégration avec indicateurs CCS (Crypto Cycle Score)
- Plus agressif en marché haussier, plus conservateur en baissier

#### 2. **Configuration Avancée**

**Symboles Prioritaires**
```javascript
BTC: ["BTC", "TBTC", "WBTC"]     // Priorité BTC natif
ETH: ["ETH", "WETH", "STETH"]    // Priorité ETH natif  
SOL: ["SOL", "JUPSOL"]           // Priorité SOL natif
```

**Allocation Sub-Groupe**
- **Proportionnelle** : Maintient les ratios actuels dans chaque groupe
- **Primary First** : Privilégie les symboles prioritaires

**Seuils de Trading**
- **Montant Minimum** : Évite les micro-trades (ex: 25 USD)
- **Filtrage Portfolio** : Ignore les positions < seuil (ex: 10 USD)

#### 3. **Génération du Plan**

Cliquez sur **🎯 Générer le Plan** pour obtenir :

**Résumé du Plan**
- **Valeur Totale** : 453,041 USD
- **Actions Nécessaires** : 12 trades
- **Volume de Trading** : 25,430 USD  
- **Frais Estimés** : 127 USD

**Tableau des Actions**

| Groupe | Symbol | Action | Montant USD | Quantité | Prix | Exchange | Exec Hint |
|--------|--------|--------|-------------|----------|------|----------|-----------|
| Others | LINK | SELL | -5,000 | 312.5 | 16.00 | Binance | Sell on Binance |
| BTC | BTC | BUY | +5,000 | 0.111 | 45,000 | Kraken | Buy on Kraken |

#### 4. **Fonctionnalités Avancées**

**Location-Aware Trading**
- Chaque action spécifie l'exchange exact
- Découpage intelligent si crypto sur plusieurs exchanges  
- Priorité CEX → DeFi → Cold Storage

**Exec Hints Intelligents**
- "Sell on Binance" : Transaction CEX rapide
- "Sell on Ledger Wallets (complex)" : Nécessite wallet hardware
- "Buy on Kraken" : Recommandation optimisée

**Export & Sauvegarde**
- **CSV Export** : Téléchargement du plan pour référence
- **Persistance** : Plan sauvé 30 minutes pour navigation
- **Restauration** : Récupération automatique si page fermée

### Gestion des Aliases

#### Unknown Aliases Detection

Quand le système détecte des cryptos non classifiées :

**🏷️ Unknown Aliases: 3 detected**
- `NEWCOIN` → Manual classification needed
- `TESTTOKEN` → Consider "Others" group  
- `OBSCUREALT` → Review classification

**Actions Disponibles**
- **Classification Unitaire** : Assign individuellement à un groupe
- **🤖 Suggestions Auto** : IA propose des classifications
- **🚀 Auto-Classifier** : Application automatique des suggestions
- **"Tout → Others"** : Classification rapide pour test

#### Interface Alias Manager

Accessible après génération d'un plan via **🏷️ Aliases**.

**Fonctionnalités**
- **Recherche en Temps Réel** : Filtrage par nom ou groupe
- **Classification par Lot** : Sélection multiple pour actions groupées  
- **Suggestions IA** : 11 catégories avec patterns automatiques
- **Statistiques** : Couverture et répartition des classifications

---

## 🛡️ Gestion des Risques

### Risk Dashboard

Interface dédiée : `static/risk-dashboard.html` ou **🛡️ Risk Dashboard**.

#### 1. **Métriques Core de Risque**

**Value at Risk (VaR)**
- **VaR 95%** : Perte potentielle max 95% du temps
- **CVaR 95%** : Expected Shortfall - perte moyenne des 5% pires cas
- **Période** : Calculs sur 30 jours rolling

**Ratios de Performance**  
- **Sharpe Ratio** : Rendement ajusté au risque (>1 = bon)
- **Sortino Ratio** : Variante Sharpe sur downside uniquement
- **Calmar Ratio** : Rendement annuel / Max Drawdown

**Métriques de Volatilité**
- **Volatilité 30J** : Écart-type des rendements quotidiens
- **Max Drawdown** : Plus grosse chute depuis un sommet
- **Skewness & Kurtosis** : Asymétrie et queues de distribution

#### 2. **Analyse de Corrélation**

**Matrice de Corrélation**
- Heatmap interactive de toutes vos cryptos
- Identification des positions redondantes  
- Opportunités de diversification

**Analyse PCA (Principal Component Analysis)**
- Réduction de dimensionalité de votre portfolio
- Score de diversification objective
- Composantes principales explicatives

#### 3. **Tests de Stress Historiques**

**Scénarios Crypto Majeurs**
- **COVID-19 Crash (Mars 2020)** : Impact -52% sur 30 jours
- **Bear Market 2018** : Correction -78% sur 365 jours  
- **Luna/FTX Collapse (2022)** : Crash -41% sur 7 jours
- **Scenarios Composites** : Combinaisons pessimistes

**Résultats par Asset**
- Impact individuel par crypto détenue
- Resilience ranking de vos holdings
- Recommandations de hedge/protection

#### 4. **Système d'Alertes Intelligent**

**Alertes Multi-Niveaux**
- 🟢 **Info** : Changements notables mais normaux
- 🟡 **Warning** : Seuils d'attention dépassés
- 🔴 **Critical** : Action immédiate recommandée

**Exemples d'Alertes**
- "Portfolio VaR 95% dépasse -15% (actuellement -18%)"
- "Corrélation BTC-ETH anormalement haute : 0.91"  
- "Max Drawdown atteint nouveau record : -23%"

---

## 🚀 Trading & Exécution

### Dashboard d'Exécution

Interface temps réel : `static/execution.html` ou **🚀 Execute**.

#### 1. **Status des Connexions**

**Surveillance Live**
- **Kraken API** : ✅ Healthy (156ms)
- **Binance API** : ✅ Healthy (203ms)  
- **CoinGecko API** : ⚠️ Degraded (1.2s)
- **Portfolio Data** : ✅ Fresh (Updated 2min ago)

#### 2. **Exécution de Plans**

**Workflow Complet**
1. **Import Plan** : Depuis interface Rebalance
2. **Validation** : Safety checks et simulation
3. **Exécution** : Trades automatisés ou manuels
4. **Monitoring** : Suivi temps réel des ordres
5. **Rapport** : Résultats et analytics post-trade

**Modes d'Exécution**
- **Simulation** : Test complet sans trades réels
- **Dry Run** : Validation avec prix réels mais sans exécution
- **Live Trading** : Exécution réelle (avec confirmations)

#### 3. **Gestion des Ordres**

**Types d'Ordres Supportés**
- **Market Orders** : Exécution immédiate au prix marché
- **Limit Orders** : Exécution à prix fixé ou mieux
- **Stop Loss** : Protection contre les baisses
- **OCO Orders** : One-Cancels-Other (fonctionnalité avancée)

**Monitoring en Temps Réel**
```
Order #12034 - BTC/USD
Status: PARTIALLY_FILLED
Progress: 0.075 / 0.111 BTC (67.5%)
Avg Price: $44,950 (Target: $45,000)
Est. Completion: 2 minutes
```

### Execution History & Analytics

Interface dédiée : `static/execution_history.html` ou **📈 History**.

#### 1. **Historique Complet**

**Session de Trading**
```
Session #789 - 2024-08-24 14:30:00
Portfolio Value: $453,041 → $455,127 (+0.46%)
Total Trades: 12
Successful: 11 (91.7%)
Failed: 1 (Network timeout - LINK sell)
Total Fees: $127.45
Net P&L: +$1,958.55
```

#### 2. **Analytics de Performance**

**Métriques de Trading**
- **Win Rate** : % de trades profitables
- **Average Trade P&L** : P&L moyen par trade
- **Sharpe des Trades** : Qualité ajustée au risque
- **Max Adverse Excursion** : Pire moment pendant l'exécution

**Comparaison Temporelle**  
- Performance vs Buy & Hold
- Impact du rebalancement sur le rendement
- Attribution des gains (allocation vs sélection vs timing)

---

## 📊 Analytics Avancées

### Interface Analytics

Fonctionnalités intégrées dans Dashboard et interfaces spécialisées.

#### 1. **Performance Attribution**

**Méthode Brinson-Fachler**
- **Allocation Effect** : Impact du choix de groupes crypto
- **Selection Effect** : Impact du choix d'assets dans les groupes
- **Interaction Effect** : Effets croisés allocation × sélection

**Exemple de Résultats**
```
Total Return: +23.4%
Benchmark (BTC): +19.8%
Alpha: +3.6%

Attribution Breakdown:
- Allocation Effect: +1.5% (Good group selection)  
- Selection Effect: +2.1% (Good asset picking)
- Interaction: +0.3% (Minor cross-effects)
```

#### 2. **Backtesting Engine**

**Tests de Stratégies**
- Test de différentes allocations cibles sur période historique
- Comparaison avec benchmarks (BTC, ETH, 50/50, etc.)
- Prise en compte des coûts de transaction réels
- Optimisation de fréquence de rebalancement

#### 3. **Optimisation Continue**

**Recommandations Dynamiques**
- Ajustements d'allocation basés sur cycles crypto
- Identification d'opportunités de rebalancement
- Alertes de deviation par rapport aux cibles
- Suggestions de prises de profits ou accumulation

---

## 🔍 Surveillance & Monitoring

### Interface Monitoring Avancée

Interface technique : `static/monitoring-unified.html` ou **🔍 Monitor**.

#### 1. **Status Système Global**

**Indicateurs Principaux**
- **Status Global** : 🟢 HEALTHY
- **Total Exchanges** : 4 surveillés
- **Exchanges Sains** : 3/4 (75%)  
- **Temps Réponse Moy** : 234ms
- **Disponibilité** : 99.2%
- **Alertes Actives** : 1 warning

#### 2. **Monitoring par Exchange**

**Exemple Kraken**
```
🟢 KRAKEN - Healthy
Uptime: 99.7% (24h)
Response Time: 156ms (avg)  
Last Check: 30 seconds ago
Error Rate: 0.1%
```

**Exemple Binance**
```
🟡 BINANCE - Degraded  
Uptime: 98.2% (24h)
Response Time: 847ms (slow)
Last Check: 45 seconds ago  
Warning: High latency detected
```

#### 3. **Analytics et Tendances**

**Onglet Analytics**
- Statistiques globales sur 24h
- Performances par exchange avec scoring
- Métriques de fiabilité et recommandations
- Graphiques de tendances de performance

**Onglet Trends**
- Analyse des tendances de performance
- Direction générale par exchange (improving/stable/degrading)
- Indicateurs visuels de health trending
- Prédictions de stabilité

#### 4. **Système d'Alertes**

**Types d'Alertes**
- **High Latency** : Temps de réponse > seuil
- **Connection Error** : Échecs de connexion répétés
- **Data Anomaly** : Données suspectes ou incohérentes  
- **Service Degraded** : Performance sous les standards

**Gestion des Alertes**
- Résolution manuelle via interface
- Auto-resolution après temps de cooldown
- Historique complet des alertes
- Notifications multi-canaux (future feature)

---

## 🔄 Workflows Recommandés

### Workflow Débutant (Premier Usage)

#### 1. **Setup Initial (30 minutes)**
```
⚙️ Settings → Configurer source données + clés API
🏠 Dashboard → Vérifier chargement portfolio  
⚖️ Rebalance → Test avec cibles simples (BTC 50%, ETH 50%)
🏷️ Aliases → Classifier unknown tokens
```

#### 2. **Analyse Portfolio (15 minutes)**
```
🏠 Dashboard → Analyser métriques et graphiques
🛡️ Risk → Vérifier scores de risque et volatilité
📊 Analytics → Examiner performance vs benchmarks
```

#### 3. **Premier Rebalancement (20 minutes)**
```
⚖️ Rebalance → Définir cibles conservatives
🎯 Générer Plan → Analyser actions proposées
📄 Export CSV → Sauvegarde pour référence
🚀 Execute → Mode simulation pour test
```

### Workflow Intermédiaire (Usage Régulier)

#### 1. **Check Hebdomadaire (10 minutes)**
```
🏠 Dashboard → Vérification métriques clés
🛡️ Risk → Contrôle dérive de risque  
🔍 Monitor → Status système et connexions
```

#### 2. **Rebalancement Mensuel (45 minutes)**
```  
⚖️ Rebalance → Ajustement cibles selon marché
🤖 IA Classification → Mise à jour taxonomie
🎯 Plan Avancé → Optimisation avec exec hints
🚀 Exécution → Simulation puis exécution réelle
📈 History → Analyse post-trade performance
```

### Workflow Expert (Gestion Active)

#### 1. **Monitoring Quotidien (5 minutes)**
```
🔍 Monitor → Check alertes et performance exchanges
🛡️ Risk → Surveillance VaR et corrélations
📊 Trends → Évolution des métriques portfolio
```

#### 2. **Optimisation Continue (2h/semaine)**
```
📈 Analytics → Deep dive attribution performance
🧠 AI Classification → Optimisation taxonomie avancée
⚖️ Dynamic Targets → Ajustement selon cycles crypto
🎯 Backtesting → Test nouvelles stratégies
🚀 Execution → Automation avec safety checks
```

#### 3. **Reporting Mensuel (1h/mois)**
```
📊 Performance Report → Génération rapport complet
🛡️ Risk Assessment → Analyse évolution profil risque
🔄 Strategy Review → Évaluation et ajustements stratégie
📈 Benchmark Analysis → Comparaison vs indices et pairs
```

---

## 🆘 Troubleshooting

### Problèmes Courants

#### 1. **"Portfolio vide ou erreur de chargement"**

**Causes Possibles :**
- Clés API CoinTracking incorrectes
- Fichier CSV manquant ou format incorrect  
- Problème de connexion internet

**Solutions :**
```bash
# 1. Vérifier configuration
curl http://127.0.0.1:8000/debug/ctapi

# 2. Tester avec données stub  
Settings → Source → "Stub (Demo Data)"

# 3. Vérifier clés API
Settings → API Keys → Re-enter credentials
```

#### 2. **"Impossible de générer un plan de rebalancement"**

**Causes Possibles :**
- Cibles ne totalisent pas 100%
- Portfolio trop petit (< min trade size)
- Tokens non classifiés bloquants

**Solutions :**
- Vérifier somme des pourcentages = 100%
- Réduire min_trade_usd dans paramètres  
- Classifier les unknown aliases

#### 3. **"Interfaces ne se chargent pas correctement"**

**Causes Possibles :**
- API server non démarré
- Port 8000 occupé par autre application
- Cache navigateur corrompu

**Solutions :**
```bash
# Redémarrer serveur
uvicorn api.main:app --reload --port 8000

# Changer de port si nécessaire
uvicorn api.main:app --reload --port 8001

# Clear cache navigateur
Ctrl+F5 ou navigation privée
```

#### 4. **"Données de prix incorrectes ou manquantes"**

**Causes Possibles :**
- CoinGecko API rate limited
- Symboles crypto non reconnus
- Mode pricing mal configuré

**Solutions :**
- Settings → Pricing → Basculer vers "Local"  
- Attendre 1 minute pour rate limit reset
- Vérifier/ajouter clé CoinGecko Pro

### Logs et Debugging

#### 1. **Logs Serveur**

Le serveur affiche des logs détaillés en mode développement :

```
INFO:     Started server process
INFO:     Waiting for application startup.
DEBUG:    Portfolio loading: 47 assets, $453,041 total
WARNING:  High latency detected for Kraken API: 1.2s
ERROR:    Failed to fetch price for NEWCOIN: symbol not found
```

#### 2. **Debug Endpoints**

**Health Check General**
```bash
curl http://127.0.0.1:8000/healthz
# → {"status": "ok", "timestamp": "..."}
```

**Debug CoinTracking Spécifique**
```bash  
curl http://127.0.0.1:8000/debug/ctapi
# → Status détaillé connexion CT
```

**Debug Clés API**
```bash
curl http://127.0.0.1:8000/debug/api-keys
# → Status des clés (masquées)
```

#### 3. **Console Navigateur**

Ouvrez les DevTools (F12) pour voir les logs frontend :

```javascript
// Logs normaux
Portfolio loaded: 47 assets, $453,041
Plan generated: 12 actions, net=0

// Erreurs courantes  
API Error 422: Target percentages must sum to 100%
Network Error: Failed to fetch portfolio data
```

### Support et Ressources

#### Documentation Complète
- **README.md** : Guide principal et overview  
- **TECHNICAL_ARCHITECTURE.md** : Architecture détaillée
- **API_REFERENCE.md** : Documentation API complète
- **DEVELOPER_GUIDE.md** : Guide pour développeurs

#### Communauté et Support
- **Issues GitHub** : Reporting bugs et feature requests
- **Discussions** : Questions et partage d'expérience  
- **Wiki** : Documentation communautaire
- **Release Notes** : Nouvelles fonctionnalités et corrections

---

**🎉 Félicitations ! Vous maîtrisez maintenant le Crypto Rebalancer. Cette plateforme professionnelle vous accompagnera dans l'optimisation continue de votre portfolio crypto. N'hésitez pas à explorer les fonctionnalités avancées et à partager vos retours d'expérience !**
