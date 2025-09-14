# Alert System Unification Plan

## Current Fragmented State

We have **4 independent alert systems** with overlapping functionality:

### 1. Main AlertEngine (services/alerts/alert_engine.py) ✅ KEEP
- **Purpose**: Sophisticated ML-powered risk alerts, Phase 2/3 system
- **Features**: Multi-timeframe analysis, cross-asset correlation, VaR alerts, phase-aware alerting
- **Alert Types**: VOL_Q90_CROSS, REGIME_FLIP, CORR_HIGH, CONTRADICTION_SPIKE, etc.
- **Status**: Primary system, fully featured, this is our TARGET

### 2. RiskAlert + AlertSystem (services/risk_management.py) ❌ MIGRATE
- **Purpose**: Basic risk threshold monitoring
- **Features**: VaR thresholds, correlation alerts, concentration alerts
- **Alert Types**: RISK_THRESHOLD, CORRELATION, CONCENTRATION, MARKET_STRESS
- **Status**: Redundant with AlertEngine's advanced risk features

### 3. Alert + AlertManager (services/notifications/alert_manager.py) ❌ MIGRATE  
- **Purpose**: General execution/system alerts
- **Features**: Portfolio drift, execution failures, performance anomalies
- **Alert Types**: PORTFOLIO_DRIFT, EXECUTION_FAILURE, PERFORMANCE_ANOMALY, API_CONNECTIVITY
- **Status**: Should be integrated into AlertEngine as new alert types

### 4. Connection Monitor Alert (services/monitoring/connection_monitor.py) ❌ MIGRATE
- **Purpose**: Exchange connection health monitoring
- **Features**: Connection status, response time, success rate tracking
- **Alert Types**: Connection degradation, API failures
- **Status**: Should feed into AlertEngine as CONNECTION_HEALTH alert type

## Unification Strategy

### Phase 1: Extend Main AlertEngine with Missing Alert Types

**Add new AlertType enum values to services/alerts/alert_types.py:**
```python
# From notifications/alert_manager.py
PORTFOLIO_DRIFT = "portfolio_drift"
EXECUTION_FAILURE = "execution_failure" 
PERFORMANCE_ANOMALY = "performance_anomaly"
API_CONNECTIVITY = "api_connectivity"

# From monitoring/connection_monitor.py  
CONNECTION_HEALTH = "connection_health"
EXCHANGE_OFFLINE = "exchange_offline"

# From risk_management.py (that aren't already covered)
RISK_CONCENTRATION_LEGACY = "risk_concentration_legacy"  # distinguish from existing RISK_CONCENTRATION
```

### Phase 2: Create Migration Adapters

**Create adapter classes that translate old alert formats to new AlertEngine format:**
- `RiskManagementAdapter` - converts RiskAlert → Alert
- `NotificationAdapter` - converts notification Alert → Alert  
- `ConnectionAdapter` - converts connection Alert → Alert

### Phase 3: Update Alert Generators

**Modify the systems that generate alerts to use AlertEngine instead:**
- `services/risk_management.py` → call AlertEngine.create_alert()
- `services/notifications/alert_manager.py` → call AlertEngine.create_alert()
- `services/monitoring/connection_monitor.py` → call AlertEngine.create_alert()

### Phase 4: Update Alert Consumers

**Update code that reads alerts to use AlertEngine endpoints:**
- Update any frontend code reading from old alert sources
- Update any monitoring/reporting that relies on old alert formats
- Ensure backwards compatibility during transition

### Phase 5: Remove Dead Code

**After migration is complete and tested:**
- Remove old AlertSystem, AlertManager, connection Alert classes
- Clean up unused imports and dependencies
- Update tests to use unified AlertEngine

## Benefits of Unification

1. **Single Source of Truth**: All alerts go through one system
2. **Consistent API**: One set of endpoints for all alert operations  
3. **Advanced Features**: All alerts benefit from ML, phase-aware logic, rate limiting, etc.
4. **Better UX**: Unified dashboard, consistent acknowledge/snooze across all alert types
5. **Easier Maintenance**: One system to maintain instead of four
6. **Better Monitoring**: Unified metrics and observability

## Implementation Steps

1. ✅ **Fix AlertEngine bugs** (completed)
2. 🔄 **Add new alert types to AlertEngine**
3. 📝 **Create migration adapters** 
4. 🔧 **Update alert generators**
5. 🎨 **Update alert consumers**
6. 🧹 **Remove dead code**

## Risk Mitigation

- **Gradual Migration**: Migrate one system at a time
- **Backwards Compatibility**: Keep old systems running during transition
- **Testing**: Extensive testing at each step
- **Rollback Plan**: Ability to revert if issues arise
- **Monitoring**: Watch for any missed alerts during transition