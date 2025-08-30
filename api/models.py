"""
Modèles Pydantic pour la validation des entrées API
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime


class APIResponse(BaseModel):
    """Modèle de base pour toutes les réponses API"""
    ok: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """Modèle pour les réponses d'erreur"""
    ok: bool = False
    error: str
    message: str
    details: Optional[Any] = None
    path: Optional[str] = None


class APIKeysRequest(BaseModel):
    """Modèle pour la mise à jour des clés API"""
    coingecko_api_key: Optional[str] = Field(None, min_length=10, max_length=100)
    cointracking_api_key: Optional[str] = Field(None, min_length=10, max_length=100)
    cointracking_api_secret: Optional[str] = Field(None, min_length=10, max_length=100)
    fred_api_key: Optional[str] = Field(None, min_length=10, max_length=100)
    
    @field_validator('*', mode='before')
    @classmethod
    def remove_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class PortfolioMetricsRequest(BaseModel):
    """Modèle pour les requêtes de métriques de portfolio"""
    source: str = Field(default="cointracking", pattern="^(cointracking|stub|cointracking_api)$")
    include_performance: bool = True
    cache_ttl: int = Field(default=300, ge=0, le=3600)  # 0-1 heure


class RebalanceRequest(BaseModel):
    """Modèle pour les requêtes de rebalancing"""
    target_allocation: Dict[str, float] = Field(..., min_items=1)
    max_deviation: float = Field(default=0.05, ge=0.01, le=0.5)  # 1-50%
    min_trade_amount_usd: float = Field(default=50.0, ge=10.0, le=10000.0)
    dry_run: bool = True
    
    @field_validator('target_allocation')
    @classmethod
    def validate_allocation_sum(cls, v):
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):  # Tolérance de 1%
            raise ValueError("Target allocation must sum to approximately 1.0")
        return v
    
    @field_validator('target_allocation')
    @classmethod
    def validate_allocation_values(cls, v):
        for symbol, allocation in v.items():
            if not (0.0 <= allocation <= 1.0):
                raise ValueError(f"Allocation for {symbol} must be between 0 and 1")
        return v


class RiskAnalysisRequest(BaseModel):
    """Modèle pour les demandes d'analyse de risque"""
    lookback_days: int = Field(default=30, ge=7, le=365)
    confidence_level: float = Field(default=0.95, ge=0.9, le=0.99)
    include_correlations: bool = True
    include_stress_testing: bool = False


class TradingPairRequest(BaseModel):
    """Modèle pour les paires de trading"""
    base_asset: str = Field(..., min_length=1, max_length=20)
    quote_asset: str = Field(..., min_length=1, max_length=20)
    exchange: str = Field(..., pattern="^(binance|kraken|coinbase)$")
    
    @field_validator('base_asset', 'quote_asset')
    @classmethod
    def uppercase_symbols(cls, v):
        return v.upper().strip()


class OrderRequest(BaseModel):
    """Modèle pour les ordres de trading"""
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(buy|sell)$")
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)
    exchange: str = Field(..., pattern="^(binance|kraken|coinbase)$")
    dry_run: bool = True
    
    @model_validator(mode='after')
    @classmethod
    def price_required_for_limit(cls, model):
        if model.order_type == 'limit' and model.price is None:
            raise ValueError("Price is required for limit orders")
        return model


class ConfigUpdateRequest(BaseModel):
    """Modèle pour la mise à jour de configuration"""
    data_source: Optional[str] = Field(None, pattern="^(cointracking|stub|cointracking_api)$")
    pricing_source: Optional[str] = Field(None, pattern="^(local|auto)$")
    cache_ttl: Optional[int] = Field(None, ge=0, le=3600)
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class HistoryRequest(BaseModel):
    """Modèle pour les requêtes d'historique"""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    exchange: Optional[str] = Field(None, pattern="^(binance|kraken|coinbase)$")
    
    @model_validator(mode='after')
    @classmethod
    def end_date_after_start(cls, model):
        if model.start_date and model.end_date and model.end_date < model.start_date:
            raise ValueError("End date must be after start date")
        return model