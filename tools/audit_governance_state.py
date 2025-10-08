#!/usr/bin/env python3
"""
Audit Governance State - Diagnostique le mode Manual et les policies
"""

import asyncio
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.execution.governance import governance_engine
from datetime import datetime


async def main():
    print("=" * 60)
    print("AUDIT GOVERNANCE STATE")
    print("=" * 60)

    # Get current state
    state = await governance_engine.get_current_state()

    print(f"\n[STATUS] GOVERNANCE MODE: {state.governance_mode.upper()}")
    print(f"[STATUS] SYSTEM STATUS: {state.system_status}")
    print(f"[STATUS] LAST UPDATE: {state.last_update}")

    # Check Manual mode + policy override
    print(f"\n[MANUAL] MANUAL POLICY CHECK:")
    if state.last_applied_policy:
        print(f"   [OK] last_applied_policy EXISTS")
        print(f"   |- cap_daily: {state.last_applied_policy.cap_daily:.1%}")
        print(f"   |- mode: {state.last_applied_policy.mode}")
        print(f"   |- ramp_hours: {state.last_applied_policy.ramp_hours}h")
        print(f"   '- notes: {state.last_applied_policy.notes}")

        if state.last_manual_policy_update:
            age = (datetime.now() - state.last_manual_policy_update).total_seconds() / 3600
            print(f"   [TIME] Last manual update: {age:.1f}h ago")
    else:
        print(f"   [NONE] NO manual policy override")

    # Current execution policy
    print(f"\n[POLICY] CURRENT EXECUTION POLICY:")
    policy = state.execution_policy
    print(f"   |- mode: {policy.mode}")
    print(f"   |- cap_daily: {policy.cap_daily:.1%}")
    print(f"   |- ramp_hours: {policy.ramp_hours}h")
    print(f"   |- signals_ttl: {policy.signals_ttl_seconds}s")
    print(f"   |- plan_cooldown: {policy.plan_cooldown_hours}h")
    print(f"   '- notes: {policy.notes}")

    # ML Signals
    print(f"\n[ML] ML SIGNALS:")
    signals = state.signals
    signals_age = (datetime.now() - signals.as_of).total_seconds()
    print(f"   |- as_of: {signals.as_of} ({signals_age:.0f}s ago)")
    print(f"   |- decision_score: {signals.decision_score:.3f}")
    print(f"   |- confidence: {signals.confidence:.3f}")
    print(f"   |- contradiction_index: {signals.contradiction_index:.3f}")
    print(f"   |- blended_score: {signals.blended_score}")
    print(f"   '- sources: {', '.join(signals.sources_used)}")

    # Hysteresis state
    print(f"\n[HYSTERESIS] HYSTERESIS STATE:")
    print(f"   |- _last_cap: {governance_engine._last_cap:.1%}")
    print(f"   |- _prudent_mode: {governance_engine._prudent_mode}")
    print(f"   |- _alert_cap_reduction: {governance_engine._alert_cap_reduction:.1%}")
    print(f"   |- _var_hysteresis_state: {governance_engine._var_hysteresis_state}")
    print(f"   '- _stale_hysteresis_state: {governance_engine._stale_hysteresis_state}")

    # Freeze status
    print(f"\n[FREEZE] FREEZE STATUS:")
    freeze_status = governance_engine.get_freeze_status()
    if freeze_status['is_frozen']:
        print(f"   [WARN] SYSTEM IS FROZEN")
        print(f"   |- freeze_type: {freeze_status['freeze_type']}")
        print(f"   |- remaining: {freeze_status.get('remaining_minutes', 'N/A')} min")
        print(f"   '- message: {freeze_status['status_message']}")
    else:
        print(f"   [OK] System operational (not frozen)")

    # Diagnostic
    print(f"\n[DIAGNOSTIC] DIAGNOSTIC:")

    if state.governance_mode == 'manual' and state.last_applied_policy:
        print(f"   [WARN] WARNING: Manual mode with policy override active!")
        print(f"      -> Cap is fixed at {state.last_applied_policy.cap_daily:.1%}")
        print(f"      -> This BYPASSES all automatic cap calculation")
        print(f"      -> To fix: Disable manual mode or clear last_applied_policy")

    if signals_age > 3600:
        print(f"   [WARN] WARNING: Signals are stale ({signals_age/3600:.1f}h old)")
        print(f"      -> This may trigger error/stale cap reduction")

    if governance_engine._alert_cap_reduction > 0:
        print(f"   [WARN] WARNING: Alert cap reduction active (-{governance_engine._alert_cap_reduction:.1%})")
        print(f"      -> This reduces the final cap")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
