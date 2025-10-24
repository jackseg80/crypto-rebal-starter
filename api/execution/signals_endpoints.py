"""
Endpoints de gestion des signaux ML

Ces endpoints permettent de mettre à jour et recalculer les signaux ML
utilisés par le système de gouvernance.
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
import logging
import asyncio
from datetime import datetime

from services.execution.governance import governance_engine
from .models import UpdateSignalsRequest, RecomputeSignalsRequest

# Import RBAC from alerts (shared dependency)
try:
    from api.alerts_endpoints import User, require_role
except ImportError:
    # Fallback si alerts_endpoints pas encore disponible
    class User:
        def __init__(self, username: str = "system", roles: List[str] = None):
            self.username = username
            self.roles = roles or ["approver", "governance_admin"]

    def require_role(required_role: str):
        def dependency(current_user: User = Depends(lambda: User())):
            return current_user
        return dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution/governance", tags=["signals"])

# Variables globales pour le recompute
_LAST_RECOMPUTE_TS = 0.0
_RECOMPUTE_WINDOW = []  # timestamps for burst control (last 10s)
_RECOMPUTE_CACHE = {}   # idempotency cache: key -> {response, ts}
_RECOMPUTE_LOCK = asyncio.Lock()  # Mutex pour éviter recompute concurrent


@router.post("/signals/update")
async def update_ml_signals(request: UpdateSignalsRequest):
    """
    Mettre à jour des champs de signaux ML maintenus côté gouvernance.
    Actuellement: accepte `blended_score` (0-100) pour activer les garde-fous backend.
    """
    try:
        # Ensure we have a current state
        state = await governance_engine.get_current_state()
        signals = state.signals

        # Update blended score if provided
        if request.blended_score is not None:
            try:
                # Attach blended score directly to signals model
                setattr(signals, 'blended_score', float(request.blended_score))
            except Exception:
                # Graceful fallback if assignment fails
                pass

        return {
            "success": True,
            "updated": {
                "blended_score": getattr(signals, 'blended_score', None)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error updating ML signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/signals/recompute")
async def recompute_ml_signals(
    request: RecomputeSignalsRequest,
    current_user: User = Depends(require_role("governance_admin")),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
):
    """
    Recompute blended score server-side from components and attach to governance signals.
    Phase 2B: With concurrency safety mutex
    """
    # Phase 2B: Acquire lock to prevent concurrent recompute
    async with _RECOMPUTE_LOCK:
        try:
            global _LAST_RECOMPUTE_TS, _RECOMPUTE_WINDOW, _RECOMPUTE_CACHE

            # CSRF basic check
            if not x_csrf_token:
                raise HTTPException(status_code=403, detail="missing_csrf_token")

            # Idempotency check
            if idempotency_key and idempotency_key in _RECOMPUTE_CACHE:
                return _RECOMPUTE_CACHE[idempotency_key]["response"]

            # Simple in-process rate-limit: 1 call/sec + burst 5/10s
            now_ts = datetime.now().timestamp()
            user_id = getattr(current_user, 'username', 'unknown')

            if (now_ts - _LAST_RECOMPUTE_TS) < 1.0:
                logger.warning(f"METRICS: recompute_429_total=1 user={user_id} reason=rate_limit")
                raise HTTPException(status_code=429, detail="too_many_requests")
            _LAST_RECOMPUTE_TS = now_ts

            # Burst window
            _RECOMPUTE_WINDOW = [t for t in _RECOMPUTE_WINDOW if (now_ts - t) < 10.0]
            if len(_RECOMPUTE_WINDOW) >= 5:
                logger.warning(f"METRICS: recompute_429_total=1 user={user_id} reason=burst_limit window_size={len(_RECOMPUTE_WINDOW)}")
                raise HTTPException(status_code=429, detail="too_many_requests_burst")
            _RECOMPUTE_WINDOW.append(now_ts)

            state = await governance_engine.get_current_state()
            signals = state.signals

            # Phase 2B: Validate component freshness for 409 NeedsRefresh
            missing_components = []
            if request.ccs_mixte is None:
                missing_components.append("ccs_mixte")
            if request.onchain_score is None:
                missing_components.append("onchain_score")
            if request.risk_score is None:
                missing_components.append("risk_score")

            if missing_components:
                logger.warning(f"AUDIT_RECOMPUTE_409: user={user_id} missing_components={missing_components}")
                raise HTTPException(
                    status_code=409,
                    detail=f"NeedsRefresh: missing components {missing_components}"
                )

            # Pull components if provided; otherwise fall back to safe neutrals
            ccs_mixte = request.ccs_mixte if request.ccs_mixte is not None else 50.0
            onchain = request.onchain_score if request.onchain_score is not None else 50.0
            risk = request.risk_score if request.risk_score is not None else 50.0

            # Get previous blended score for audit trail
            blended_old = getattr(signals, 'blended_score', None)

            # Strategic blended: 50% CCS Mixte + 30% On-Chain + 20% Risk
            # Risk Score semantics: 0-100, higher = more robust (no inversion)
            blended = (ccs_mixte * 0.50) + (onchain * 0.30) + (risk * 0.20)
            blended = max(0.0, min(100.0, blended))

            try:
                setattr(signals, 'blended_score', float(blended))
                setattr(signals, 'as_of', datetime.now())
            except Exception as e:
                logger.warning(f"Failed to update blended_score on signals: {e}")

            # Phase 2A: Enriched structured audit logging with unique calc_timestamp
            policy = state.execution_policy
            calc_timestamp = datetime.now()

            # Real backend health check
            backend_status = "ok"
            try:
                # 1. Check signals freshness
                signals_age = (calc_timestamp - signals.as_of).total_seconds() if signals.as_of else 0

                # 2. Check governance engine state
                if not state or not signals:
                    backend_status = "error"
                elif signals_age > 7200:  # > 2h : critical
                    backend_status = "error"
                elif signals_age > 3600:  # 1-2h : warning
                    backend_status = "stale"

                # 3. Check policy validity
                if backend_status == "ok" and policy:
                    if not hasattr(policy, 'mode') or not hasattr(policy, 'cap_daily'):
                        backend_status = "stale"

                logger.debug(f"Backend health check: status={backend_status}, signals_age={signals_age}s")
            except Exception as e:
                logger.warning(f"Backend health check failed: {e}")
                backend_status = "error"

            audit_data = {
                "event": "recompute_blended",
                "user": getattr(current_user, 'username', 'unknown'),
                "timestamp": calc_timestamp.isoformat(),
                "calc_timestamp": calc_timestamp.isoformat(),
                "blended_old": blended_old,
                "blended_new": round(blended, 1),
                "inputs": {
                    "ccs_mixte": ccs_mixte,
                    "onchain": onchain,
                    "risk": risk
                },
                "policy_cap_before": round(policy.cap_daily * 100, 1) if policy else None,
                "policy_cap_after": round(policy.cap_daily * 100, 1) if policy else None,
                "idempotency_hit": idempotency_key in _RECOMPUTE_CACHE if idempotency_key else False,
                "backend_status": backend_status,
                "rate_limit_window": len(_RECOMPUTE_WINDOW),
                "session_id": idempotency_key[:8] if idempotency_key else "none"
            }

            # Log structured audit entry
            logger.info(f"AUDIT_RECOMPUTE: {audit_data}")
            logger.info(f"recompute_blended user={audit_data['user']} "
                       f"blended={audit_data['blended_old']}→{audit_data['blended_new']} "
                       f"inputs=({ccs_mixte},{onchain},{risk}) "
                       f"backend={backend_status} "
                       f"idempotency={'HIT' if audit_data['idempotency_hit'] else 'NEW'}")

            # Simple metrics tracking
            try:
                logger.info(f"METRICS: recompute_ok_total=1 user={audit_data['user']} backend_status={backend_status}")
                if audit_data['idempotency_hit']:
                    logger.info(f"METRICS: recompute_idempotency_hit_total=1 user={audit_data['user']}")
            except Exception as e:
                logger.debug(f"Failed to log recompute metrics: {e}")

            response_payload = {
                "success": True,
                "blended_score": blended,
                "blended_formula_version": "1.0",
                "timestamp": calc_timestamp.isoformat(),
                "calc_timestamp": calc_timestamp.isoformat()
            }

            # Idempotency cache
            if idempotency_key:
                try:
                    _RECOMPUTE_CACHE[idempotency_key] = {"response": response_payload, "ts": calc_timestamp.timestamp()}
                except Exception as e:
                    logger.warning(f"Failed to cache idempotent response for key {idempotency_key}: {e}")

            return response_payload
        except Exception as e:
            logger.error(f"Error recomputing ML signals: {e}")
            raise HTTPException(status_code=500, detail=str(e))
