"""Pydantic models for Wealth namespace unifying holdings across providers."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
import logging

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)


class WealthBaseModel(BaseModel):
    """Base model enforcing strict typing and immutability."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


class AccountModel(WealthBaseModel):
    """Normalized investment account descriptor."""

    id: str = Field(..., description="Stable account identifier")
    provider: Literal["crypto", "saxo", "banks"]
    type: str = Field(..., description="Account type or venue name")
    currency: str = Field(..., min_length=3, max_length=3)


class InstrumentModel(WealthBaseModel):
    """Cross-provider instrument metadata."""

    id: str = Field(..., description="Internal instrument identifier")
    symbol: str = Field(..., description="Display symbol")
    isin: Optional[str] = Field(default=None, description="ISIN when available")
    name: str = Field(..., description="Readable instrument name")
    asset_class: Literal[
        "CRYPTO",
        "EQUITY",
        "ETF",
        "BOND",
        "CASH",
        "COMMODITY",
        "REIT",
        "FX",
    ]
    sector: Optional[str] = Field(default=None, description="Sector bucket, optional")
    region: Optional[str] = Field(default=None, description="Geographical exposure")


class PositionModel(WealthBaseModel):
    """Position snapshot normalized across modules."""

    instrument_id: str
    quantity: float
    avg_price: Optional[float] = Field(default=None, description="Average acquisition price")
    currency: str = Field(..., min_length=3, max_length=3)
    market_value: Optional[float] = Field(default=None, description="Mark-to-market value")
    pnl: Optional[float] = Field(default=None, description="Unrealized profit and loss")
    weight: Optional[float] = Field(default=None, description="Portfolio weight in decimal form")
    tags: List[str] = Field(default_factory=list, description="Free-form classification tags")


class TransactionModel(WealthBaseModel):
    """Transaction history entry in normalized format."""

    instrument_id: str
    date: datetime
    type: Literal["BUY", "SELL", "DIV", "FEE", "FX", "DEPOSIT", "WITHDRAW"]
    qty: Optional[float] = Field(default=None, description="Quantity transacted")
    price: Optional[float] = Field(default=None, description="Execution price")
    fees: Optional[float] = Field(default=None, description="Fees charged in trade currency")
    currency: str = Field(..., min_length=3, max_length=3)


class PricePoint(WealthBaseModel):
    """Single price observation for an instrument."""

    instrument_id: str
    ts: datetime
    price: float
    currency: str = Field(..., min_length=3, max_length=3)
    source: str = Field(..., description="Pricing source identifier")


class ProposedTrade(WealthBaseModel):
    """Suggested trade action for rebalancing preview."""

    instrument_id: str
    action: Literal["BUY", "SELL", "HOLD"]
    quantity: float
    rationale: str
    est_cost: Optional[float] = Field(default=None, description="Estimated trade cost in account currency")


class BankAccountInput(BaseModel):
    """Input model for creating/updating bank accounts (mutable for forms)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    bank_name: str = Field(..., min_length=1, max_length=100, description="Bank institution name")
    account_type: Literal["current", "savings", "pel", "livret_a", "other"] = Field(
        ..., description="Account type classification"
    )
    balance: float = Field(..., ge=0, description="Current account balance")
    currency: str = Field(..., pattern="^(CHF|EUR|USD|GBP)$", description="Account currency (ISO 4217)")


class BankAccountOutput(WealthBaseModel):
    """Output model for bank accounts with computed fields."""

    id: str = Field(..., description="Unique account identifier")
    bank_name: str = Field(..., description="Bank institution name")
    account_type: str = Field(..., description="Account type classification")
    balance: float = Field(..., description="Current account balance")
    currency: str = Field(..., description="Account currency (ISO 4217)")
    balance_usd: Optional[float] = Field(default=None, description="Balance converted to USD")


# ===== Patrimoine Models (Phase 1 - Oct 2025) =====


class PatrimoineItemInput(BaseModel):
    """Input model for creating/updating patrimoine items (mutable for forms)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Item name (e.g., 'Maison Lyon', 'Revolut')")
    category: Literal["liquidity", "tangible", "liability", "insurance"] = Field(
        ..., description="Item category"
    )
    type: Literal[
        "bank_account",
        "neobank",
        "cash",
        "real_estate",
        "vehicle",
        "precious_metals",
        "credit_card",
        "mortgage",
        "loan",
        "life_insurance",
        "investment_insurance",
    ] = Field(..., description="Item type within category")
    value: float = Field(..., description="Current value (positive for assets, negative for liabilities)")
    currency: str = Field(..., pattern="^(CHF|EUR|USD|GBP)$", description="Currency (ISO 4217)")
    acquisition_date: Optional[str] = Field(default=None, description="Acquisition date (YYYY-MM-DD)")
    notes: Optional[str] = Field(default=None, max_length=500, description="Free-form notes")
    metadata: Optional[dict] = Field(default_factory=dict, description="Type-specific metadata (JSON)")


class PatrimoineItemOutput(WealthBaseModel):
    """Output model for patrimoine items with computed fields."""

    id: str = Field(..., description="Unique item identifier")
    name: str = Field(..., description="Item name")
    category: str = Field(..., description="Item category")
    type: str = Field(..., description="Item type")
    value: float = Field(..., description="Current value")
    currency: str = Field(..., description="Currency (ISO 4217)")
    value_usd: Optional[float] = Field(default=None, description="Value converted to USD")
    acquisition_date: Optional[str] = Field(default=None, description="Acquisition date")
    notes: Optional[str] = Field(default=None, description="Free-form notes")
    metadata: dict = Field(default_factory=dict, description="Type-specific metadata")


__all__ = [
    "AccountModel",
    "InstrumentModel",
    "PositionModel",
    "TransactionModel",
    "PricePoint",
    "ProposedTrade",
    "BankAccountInput",
    "BankAccountOutput",
    "PatrimoineItemInput",
    "PatrimoineItemOutput",
]
