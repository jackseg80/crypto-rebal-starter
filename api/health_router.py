"""
Health Router - Health Check and Utility Endpoints
Extracted from api/main.py for better organization
"""
import base64
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from api.utils import success_response, error_response

# Import configuration
from config import get_settings
settings = get_settings()
ENVIRONMENT = settings.environment

logger = logging.getLogger("crypto-rebalancer")

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Simple health check endpoint for containers"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "environment": ENVIRONMENT}


@router.get("/healthz")
async def healthz():
    """Kubernetes-style health probe"""
    return success_response({})


@router.get("/favicon.ico")
async def favicon():
    """Serve a tiny placeholder favicon to avoid 404s in the browser console."""
    try:
        # 1x1 transparent PNG
        b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO1iYl8AAAAASUVORK5CYII="
        )
        data = base64.b64decode(b64)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        # Fallback to no-content if decoding somehow fails
        logger.warning(f"Failed to decode favicon data: {e}")
        return Response(status_code=204)


@router.get("/test-simple")
async def test_simple():
    """Simple test endpoint for debugging"""
    return {"test": "working", "endpoints_loaded": True}


@router.get("/health/detailed")
async def health_detailed():
    """Endpoint de santé détaillé avec métriques complètes"""
    return success_response({
        "message": "Health detailed endpoint working!",
        "server_running": True
    })


@router.get("/api/scheduler/health")
async def scheduler_health():
    """
    Scheduler health check endpoint - shows status of all scheduled jobs.

    Returns:
        dict: Job status with last run time, duration, and errors
    """
    try:
        from api.scheduler import get_scheduler, get_job_status

        scheduler = get_scheduler()

        if scheduler is None:
            return error_response(
                "Scheduler not running (RUN_SCHEDULER != 1)",
                code=503,
                details={"enabled": False, "jobs": {}}
            )

        # Get job status
        job_status = get_job_status()

        # Get next run times
        jobs = scheduler.get_jobs()
        next_runs = {}
        for job in jobs:
            next_runs[job.id] = {
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }

        # Merge status with next runs
        for job_id, status in job_status.items():
            if job_id in next_runs:
                status["next_run"] = next_runs[job_id]["next_run"]
                status["name"] = next_runs[job_id]["name"]

        return success_response({
            "enabled": True,
            "jobs_count": len(jobs),
            "jobs": job_status,
            "next_runs": next_runs
        })

    except Exception as e:
        logger.exception("Failed to get scheduler health")
        return error_response(str(e), code=500)


@router.get("/schema")
async def schema():
    """Fallback endpoint to expose OpenAPI schema if /openapi.json isn't reachable in your env."""
    # Import app dynamically to avoid circular import
    from api.main import app
    try:
        return app.openapi()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAPI generation failed: {e}")
