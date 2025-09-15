"""
Saxo Bank API Endpoints
Handles Saxo Bank data import and portfolio management
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import logging
import tempfile
import os
from pathlib import Path
import json
from datetime import datetime

from connectors.saxo_import import SaxoImportConnector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saxo", tags=["Saxo Bank"])

# Initialize connector
saxo_connector = SaxoImportConnector()

# Data storage (in production, use proper database)
_saxo_portfolios = {}


class SaxoPosition(BaseModel):
    position_id: str
    symbol: str
    instrument: str
    quantity: float
    market_value: float
    market_value_usd: float
    currency: str
    asset_class: str
    source: str = "saxo_bank"
    import_timestamp: str


class SaxoPortfolio(BaseModel):
    portfolio_id: str
    name: str
    positions: List[SaxoPosition]
    total_market_value_usd: float
    asset_allocation: Dict[str, float]
    currency_exposure: Dict[str, float]
    created_at: str
    updated_at: str


@router.post("/import")
async def import_saxo_file(
    file: UploadFile = File(...),
    portfolio_name: str = Form(default="")
):
    """
    Import Saxo Bank CSV/XLSX file

    Returns processed portfolio data
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in saxo_connector.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Supported: {', '.join(saxo_connector.supported_formats)}"
            )

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            # Validate file structure
            validation = saxo_connector.validate_file(tmp_file_path)
            if not validation["valid"]:
                raise HTTPException(status_code=400, detail=validation["error"])

            # Process file
            result = saxo_connector.process_saxo_file(tmp_file_path)

            if not result["positions"]:
                raise HTTPException(status_code=400, detail="No valid positions found in file")

            # Generate portfolio summary
            summary = saxo_connector.get_portfolio_summary(result["positions"])

            # Create portfolio record
            portfolio_id = f"saxo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            portfolio_name = portfolio_name or f"Saxo Portfolio {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            portfolio_data = {
                "portfolio_id": portfolio_id,
                "name": portfolio_name,
                "positions": result["positions"],
                "summary": summary,
                "errors": result.get("errors", []),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "source_file": file.filename
            }

            # Store portfolio (in memory for now)
            _saxo_portfolios[portfolio_id] = portfolio_data

            logger.info(f"Successfully imported Saxo portfolio: {len(result['positions'])} positions, ${summary['total_value_usd']:,.2f} total value")

            return {
                "success": True,
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio_name,
                "positions_count": len(result["positions"]),
                "total_value_usd": summary["total_value_usd"],
                "asset_allocation": summary["asset_allocation"],
                "currency_exposure": summary["currency_exposure"],
                "top_holdings": summary["top_holdings"][:5],  # Return top 5
                "errors": result.get("errors", []),
                "created_at": portfolio_data["created_at"]
            }

        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing Saxo file: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/portfolios")
async def list_saxo_portfolios():
    """List all imported Saxo portfolios"""
    portfolios = []

    for portfolio_id, data in _saxo_portfolios.items():
        portfolios.append({
            "portfolio_id": portfolio_id,
            "name": data["name"],
            "positions_count": len(data["positions"]),
            "total_value_usd": data["summary"]["total_value_usd"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "source_file": data.get("source_file")
        })

    return {
        "portfolios": sorted(portfolios, key=lambda x: x["created_at"], reverse=True),
        "total_portfolios": len(portfolios)
    }


@router.get("/portfolios/{portfolio_id}")
async def get_saxo_portfolio(portfolio_id: str):
    """Get detailed Saxo portfolio data"""
    if portfolio_id not in _saxo_portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio = _saxo_portfolios[portfolio_id]

    return {
        "portfolio_id": portfolio_id,
        "name": portfolio["name"],
        "positions": portfolio["positions"],
        "summary": portfolio["summary"],
        "errors": portfolio.get("errors", []),
        "created_at": portfolio["created_at"],
        "updated_at": portfolio["updated_at"],
        "source_file": portfolio.get("source_file")
    }


@router.delete("/portfolios/{portfolio_id}")
async def delete_saxo_portfolio(portfolio_id: str):
    """Delete a Saxo portfolio"""
    if portfolio_id not in _saxo_portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio_name = _saxo_portfolios[portfolio_id]["name"]
    del _saxo_portfolios[portfolio_id]

    return {
        "success": True,
        "message": f"Portfolio '{portfolio_name}' deleted successfully"
    }


@router.get("/positions/{portfolio_id}")
async def get_saxo_positions(
    portfolio_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0)
):
    """Get positions for a specific portfolio with pagination"""
    if portfolio_id not in _saxo_portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    positions = _saxo_portfolios[portfolio_id]["positions"]

    # Apply pagination
    total = len(positions)
    paginated_positions = positions[offset:offset + limit]

    return {
        "positions": paginated_positions,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    }


@router.get("/summary/{portfolio_id}")
async def get_portfolio_summary(portfolio_id: str):
    """Get portfolio summary and analytics"""
    if portfolio_id not in _saxo_portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio = _saxo_portfolios[portfolio_id]
    summary = portfolio["summary"]

    # Add additional analytics
    positions = portfolio["positions"]

    # Asset class breakdown
    asset_classes = {}
    for pos in positions:
        asset_class = pos["asset_class"]
        if asset_class not in asset_classes:
            asset_classes[asset_class] = {"count": 0, "value": 0, "positions": []}

        asset_classes[asset_class]["count"] += 1
        asset_classes[asset_class]["value"] += pos["market_value_usd"]
        asset_classes[asset_class]["positions"].append({
            "symbol": pos["symbol"],
            "value": pos["market_value_usd"],
            "percentage": (pos["market_value_usd"] / summary["total_value_usd"]) * 100
        })

    return {
        "portfolio_id": portfolio_id,
        "total_value_usd": summary["total_value_usd"],
        "total_positions": summary["total_positions"],
        "asset_allocation": summary["asset_allocation"],
        "currency_exposure": summary["currency_exposure"],
        "asset_classes": asset_classes,
        "top_holdings": summary["top_holdings"],
        "updated_at": portfolio["updated_at"]
    }


@router.post("/validate")
async def validate_saxo_file(file: UploadFile = File(...)):
    """Validate Saxo file without importing"""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in saxo_connector.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Supported: {', '.join(saxo_connector.supported_formats)}"
            )

        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            validation = saxo_connector.validate_file(tmp_file_path)
            return validation

        finally:
            os.unlink(tmp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating Saxo file: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")