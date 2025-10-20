"""
Data formatting utilities and standard API response formatters.

This module provides:
1. CSV/currency/percentage formatters (existing)
2. Standard API response formatters (new) - success_response(), error_response()

Usage:
    from api.utils.formatters import success_response, error_response

    @app.get("/endpoint")
    async def endpoint():
        data = {"key": "value"}
        return success_response(data)
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import csv
import io

def to_csv(actions: List[Dict[str, Any]]) -> str:
    """Convert list of actions to CSV string"""
    if not actions:
        return ""
    
    output = io.StringIO()
    
    # Define column order
    fieldnames = [
        'symbol', 'action', 'amount', 'value_usd', 'location', 
        'current_allocation', 'target_allocation', 'drift',
        'priority', 'notes'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for action in actions:
        # Ensure all required fields exist
        row = {field: action.get(field, '') for field in fieldnames}
        writer.writerow(row)
    
    return output.getvalue()

def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string"""
    if currency.upper() == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format value as percentage string"""
    return f"{value:.{decimals}f}%"

def format_action_summary(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a summary of rebalancing actions"""
    if not actions:
        return {
            "total_actions": 0,
            "total_value": 0,
            "buy_actions": 0,
            "sell_actions": 0,
            "summary": "No actions required"
        }

    buy_actions = [a for a in actions if a.get('action') == 'buy']
    sell_actions = [a for a in actions if a.get('action') == 'sell']

    total_value = sum(float(a.get('value_usd', 0)) for a in actions)

    return {
        "total_actions": len(actions),
        "total_value": total_value,
        "buy_actions": len(buy_actions),
        "sell_actions": len(sell_actions),
        "total_value_formatted": format_currency(total_value),
        "summary": f"{len(actions)} actions totaling {format_currency(total_value)}"
    }


# ============================================================================
# Standard API Response Formatters
# ============================================================================

class StandardResponse(BaseModel):
    """
    Standard API response model.

    Attributes:
        ok: Success flag (True for success, False for errors)
        data: Response data (any JSON-serializable type)
        meta: Optional metadata (pagination, timestamps, etc.)
        error: Optional error message (only present when ok=False)
        details: Optional error details (only present when ok=False)
        timestamp: ISO 8601 timestamp of response generation
    """
    ok: bool
    data: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str


def success_response(
    data: Any,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200
) -> JSONResponse:
    """
    Create a standard success response.

    Args:
        data: Response data (any JSON-serializable type)
        meta: Optional metadata dict (e.g., {"count": 10, "page": 1})
        status_code: HTTP status code (default: 200)

    Returns:
        JSONResponse with standardized success format

    Example:
        >>> success_response({"balance": 1000}, meta={"currency": "USD"})
        {
            "ok": true,
            "data": {"balance": 1000},
            "meta": {"currency": "USD"},
            "timestamp": "2025-10-20T10:30:00.123456"
        }
    """
    response_data = {
        "ok": True,
        "data": data,
        "meta": meta or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def error_response(
    message: str,
    code: int = 500,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create a standard error response.

    Args:
        message: Human-readable error message
        code: HTTP status code (default: 500)
        details: Optional error details dict (e.g., {"field": "email", "reason": "invalid"})

    Returns:
        JSONResponse with standardized error format

    Example:
        >>> error_response("User not found", code=404, details={"user_id": "jack"})
        {
            "ok": false,
            "error": "User not found",
            "details": {"user_id": "jack"},
            "timestamp": "2025-10-20T10:30:00.123456"
        }
    """
    response_data = {
        "ok": False,
        "error": message,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    return JSONResponse(
        status_code=code,
        content=response_data
    )


def paginated_response(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 50,
    meta: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create a paginated success response.

    Args:
        items: List of items for current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Number of items per page
        meta: Optional additional metadata

    Returns:
        JSONResponse with paginated format

    Example:
        >>> paginated_response(items=[1,2,3], total=100, page=2, page_size=3)
        {
            "ok": true,
            "data": [1, 2, 3],
            "meta": {
                "pagination": {
                    "total": 100,
                    "page": 2,
                    "page_size": 3,
                    "total_pages": 34,
                    "has_next": true,
                    "has_prev": true
                }
            },
            "timestamp": "2025-10-20T10:30:00.123456"
        }
    """
    total_pages = (total + page_size - 1) // page_size  # Ceiling division

    pagination_meta = {
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }

    # Merge with additional meta if provided
    if meta:
        pagination_meta.update(meta)

    return success_response(data=items, meta=pagination_meta)


def legacy_response(
    source_used: str,
    items: List[Any],
    warnings: Optional[List[str]] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a legacy-format response for backward compatibility.

    This format is used by resolve_current_balances and similar endpoints
    that return {"source_used": "...", "items": [...]} dictionaries.

    Args:
        source_used: Data source identifier (e.g., "cointracking", "saxobank")
        items: List of data items
        warnings: Optional list of warning messages
        error: Optional error message

    Returns:
        Dict with legacy format (NOT JSONResponse)

    Example:
        >>> legacy_response("cointracking", items=[{"symbol": "BTC"}], warnings=["stale data"])
        {
            "source_used": "cointracking",
            "items": [{"symbol": "BTC"}],
            "warnings": ["stale data"]
        }

    Note:
        This is NOT wrapped in JSONResponse because it's used internally
        and returned as a dict. Use success_response() for new endpoints.
    """
    response = {
        "source_used": source_used,
        "items": items
    }

    if warnings:
        response["warnings"] = warnings

    if error:
        response["error"] = error

    return response