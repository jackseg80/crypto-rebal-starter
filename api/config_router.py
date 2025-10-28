"""
Config Router - Configuration Endpoints
Extracted from api/main.py (Phase 2D)
"""
import os
import logging
from pathlib import Path
from fastapi import APIRouter
from api.utils import success_response, error_response

router = APIRouter(prefix="/api/config", tags=["config"])
logger = logging.getLogger(__name__)

# In-memory storage for frontend configuration
_frontend_config = {"data_source": None}

@router.post("/data-source")
async def set_data_source(request: dict):
    """
    Set the data source configuration from frontend
    """
    try:
        data_source = request.get("data_source")
        if data_source in ["stub", "stub_balanced", "stub_conservative", "stub_shitcoins", "cointracking", "cointracking_api"]:
            _frontend_config["data_source"] = data_source
            logger.info(f"Data source updated to: {data_source}")
            return success_response({"data_source": data_source})
        else:
            return error_response("Invalid data source", code=400)
    except Exception as e:
        logger.error(f"Error setting data source: {e}")
        return error_response(str(e), code=500)

@router.get("/data-source")
async def get_configured_data_source():
    """
    Get the currently configured data source
    This endpoint respects frontend configuration first, then falls back to detection
    """
    try:
        # First, check if frontend has explicitly set a data source
        if _frontend_config["data_source"]:
            return success_response({"data_source": _frontend_config["data_source"]})

        # Fallback to smart detection if no explicit config
        api_key = os.getenv("COINTRACKING_API_KEY")
        api_secret = os.getenv("COINTRACKING_API_SECRET")

        if api_key and api_secret:
            return success_response({"data_source": "cointracking_api"})
        elif Path("data/raw").exists() and any(Path("data/raw").glob("*.csv")):
            return success_response({"data_source": "cointracking"})
        else:
            return success_response({"data_source": "stub"})

    except Exception as e:
        logger.error(f"Error getting data source config: {e}")
        return success_response({"data_source": "stub"})  # Safe fallback
