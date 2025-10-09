# Alert Reduction Auto-Clear - Implementation Plan

**Date** : Oct 2025
**Problem** : `clear_alert_cap_reduction()` never called → alert reduction stays active forever

---

## Current Behavior (Bug)

**Alert lifecycle** :
1. `EXEC_COST_SPIKE` triggered → `apply_alert_cap_reduction(0.03)`
2. `_alert_cap_reduction = 0.03` set
3. Cooldown 60min to prevent new reductions
4. **Reduction stays active forever** (no auto-clear)

**Impact** :
- Cap reduced from 7% to 4% indefinitely
- Only way to clear: restart server

---

## Solution: Auto-Clear After Alert Resolves

### Implementation Points

#### 1. Track Alert Resolution in AlertEngine

**File** : `services/alerts/alert_engine.py`

**Add tracking** :
```python
# In __init__
self._active_systemic_alerts = set()  # Track which alerts caused cap reduction

# In _check_systemic_conditions() after applying reduction
if success:
    self._active_systemic_alerts.add(alert.id)

# When alert resolves (acknowledged or auto-resolved)
def _on_alert_resolved(self, alert_id: str):
    if alert_id in self._active_systemic_alerts:
        self._active_systemic_alerts.remove(alert_id)

        # If no more systemic alerts, clear cap reduction
        if not self._active_systemic_alerts:
            self.governance_engine.clear_alert_cap_reduction(progressive=True)
```

#### 2. Call clear_alert_cap_reduction on Acknowledge

**File** : `api/alerts_endpoints.py`

**In acknowledge endpoint** :
```python
@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    # Existing code...
    alert_engine._on_alert_resolved(alert_id)  # Trigger clear
    return {"status": "acknowledged"}
```

#### 3. Progressive Clear (1% every 30min)

**File** : `services/execution/governance.py:757`

**Already implemented** :
```python
def clear_alert_cap_reduction(self, progressive: bool = True) -> bool:
    if progressive:
        step = 0.01  # 1 point de pourcentage
        self._alert_cap_reduction = max(0, self._alert_cap_reduction - step)
```

**Call periodically** :
- Every 30 minutes, call `clear_alert_cap_reduction(progressive=True)`
- Reduction: 3% → 2% → 1% → 0% over 90 minutes

#### 4. Add Periodic Task in GovernanceEngine

**File** : `services/execution/governance.py`

```python
# In __init__
self._last_progressive_clear = datetime.now()

# In _derive_execution_policy() before returning
# Auto-clear progressive every 30min
if self._alert_cap_reduction > 0:
    if (datetime.now() - self._last_progressive_clear).total_seconds() > 1800:  # 30min
        self.clear_alert_cap_reduction(progressive=True)
        self._last_progressive_clear = datetime.now()
        logger.info(f"Auto progressive clear: reduction now {self._alert_cap_reduction:.1%}")
```

---

## Alternative: Time-Based Expiry

Instead of tracking alert resolution, expire reduction after fixed time:

```python
# In __init__
self._alert_reduction_expires_at = None

# In apply_alert_cap_reduction()
self._alert_reduction_expires_at = datetime.now() + timedelta(hours=2)

# In _derive_execution_policy() check expiry
if self._alert_reduction_expires_at and datetime.now() > self._alert_reduction_expires_at:
    logger.warning("Alert cap reduction expired after 2h, clearing")
    self.clear_alert_cap_reduction(progressive=False)
    self._alert_reduction_expires_at = None
```

**Pros** :
- Simple, no alert tracking needed
- Automatic recovery after 2h

**Cons** :
- Fixed time may not match alert duration

---

## Recommendation

**Implement Progressive Clear (Option 4)** :
- Add periodic task in `_derive_execution_policy()`
- Every 30min, reduce by 1%
- Reduction: 3% → 2% → 1% → 0% over 90 minutes
- Simple, safe, automatic recovery

**Implementation time** : 5 minutes
**Risk** : Low (only adds auto-clear, doesn't change existing logic)

---

## Immediate Workaround

Until auto-clear implemented, users can:

1. **Restart server** : Reset `_alert_cap_reduction` to 0
2. **Manual API call** : Add endpoint to manually clear

```python
# In api/execution_endpoints.py
@router.post("/execution/governance/clear-alert-reduction")
async def clear_alert_reduction():
    from services.execution.governance import get_governance_engine
    engine = get_governance_engine()
    engine.clear_alert_cap_reduction(progressive=False)
    return {"status": "cleared", "reduction": 0.0}
```

---

## Testing

```python
# tests/unit/test_alert_cap_reduction.py

def test_auto_clear_after_30min():
    """Alert reduction should auto-clear progressively"""
    engine = GovernanceEngine()

    # Apply reduction
    engine.apply_alert_cap_reduction(0.03, "test-alert", "test")
    assert engine._alert_cap_reduction == 0.03

    # Simulate 30min pass
    engine._last_progressive_clear = datetime.now() - timedelta(minutes=31)
    policy = engine._derive_execution_policy()

    # Should have reduced by 1%
    assert engine._alert_cap_reduction == 0.02

def test_clear_expires_after_90min():
    """Alert reduction should fully clear after 90min"""
    engine = GovernanceEngine()

    # Apply reduction
    engine.apply_alert_cap_reduction(0.03, "test-alert", "test")

    # Simulate 3 clears (30min × 3 = 90min)
    for _ in range(3):
        engine._last_progressive_clear = datetime.now() - timedelta(minutes=31)
        engine._derive_execution_policy()

    # Should be fully cleared
    assert engine._alert_cap_reduction == 0.0
```

---

## Status

- **Current** : Alert reduction stays active forever (bug)
- **Fixed** : Floor 3% + preserved `_last_cap` prevent spiral down
- **Next** : Implement auto-clear (this document)
