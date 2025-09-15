"""
Version safe de smart_taxonomy_endpoints sans imports bloquants
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/taxonomy", tags=["smart_taxonomy_safe"])

@router.post("/classify")
async def classify_symbols_safe(symbols: List[str]):
    """Classification safe mode - pas d'imports lourds"""
    return {
        "status": "safe_mode",
        "message": "Smart taxonomy disabled - safe mode active",
        "symbols": symbols,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/status")
async def smart_taxonomy_status():
    """Status du système de taxonomie intelligente"""
    return {
        "status": "safe_mode", 
        "message": "Heavy imports disabled for CTRL+C compatibility"
    }