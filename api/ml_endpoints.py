"""
Machine Learning API Endpoints
ML-powered market regime detection and return forecasting
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, List, Optional
import pandas as pd
from pydantic import BaseModel
import logging

from services.ml_models import ml_pipeline, MarketRegime
from services.price_history import get_cached_history
from connectors.cointracking_api import get_current_balances

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

class TrainingRequest(BaseModel):
    """Request model for ML training"""
    assets: List[str]
    lookback_days: int = 730
    include_market_indicators: bool = True
    save_models: bool = True

class PredictionResponse(BaseModel):
    """Response model for ML predictions"""
    success: bool
    regime_prediction: Optional[Dict]
    return_predictions: Optional[Dict]
    model_status: Dict
    timestamp: str

@router.post("/train")
async def train_models(
    request: TrainingRequest,
    background_tasks: BackgroundTasks,
    source: str = Query("cointracking", description="Data source for current portfolio")
):
    """
    Train ML models for regime detection and return forecasting
    """
    
    try:
        # Validation input parameters
        if request.lookback_days < 30 or request.lookback_days > 2000:
            raise HTTPException(
                status_code=400, 
                detail="lookback_days must be between 30 and 2000 days"
            )
        
        # Get current portfolio for default assets if not specified
        if not request.assets:
            try:
                balances_response = await get_current_balances(source=source)
                if balances_response.get("items"):
                    request.assets = [item["symbol"] for item in balances_response["items"][:10]]  # Top 10 assets
                else:
                    raise HTTPException(
                        status_code=404, 
                        detail="No portfolio assets found. Please specify assets manually."
                    )
            except Exception as e:
                logger.error(f"Error fetching portfolio: {e}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to fetch portfolio data: {str(e)}"
                )
        
        # Validate assets list
        if len(request.assets) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 assets allowed for training"
            )
        
        if not request.assets:
            request.assets = ["BTC", "ETH", "SOL"]  # Fallback assets
        
        # Start training in background
        background_tasks.add_task(
            _train_models_background,
            request.assets,
            request.lookback_days,
            request.include_market_indicators,
            request.save_models
        )
        
        return {
            "success": True,
            "message": "Model training started in background",
            "assets": request.assets,
            "lookback_days": request.lookback_days,
            "estimated_duration_minutes": len(request.assets) * 2  # Rough estimate
        }
        
    except Exception as e:
        logger.error(f"Failed to start ML training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")

async def _train_models_background(assets: List[str], lookback_days: int, 
                                 include_indicators: bool, save_models: bool):
    """Background task for model training"""
    
    try:
        logger.info(f"Starting background ML training for {len(assets)} assets")
        
        # Collect price data
        price_data = {}
        for asset in assets:
            try:
                prices = get_cached_history(asset, days=lookback_days)
                if prices and len(prices) > 100:  # Minimum data requirement
                    price_data[asset] = prices
                else:
                    logger.warning(f"Insufficient data for {asset}, skipping")
            except Exception as e:
                logger.warning(f"Could not get price data for {asset}: {e}")
                continue
        
        if len(price_data) < 2:
            logger.error("Insufficient assets with price data for training")
            return
        
        # Create DataFrame
        price_df = pd.DataFrame(price_data).fillna(method='ffill').dropna()
        
        # Market indicators (placeholder - in practice would fetch from APIs)
        market_indicators = None
        if include_indicators:
            market_indicators = {
                'vix': pd.Series(np.random.normal(20, 5, len(price_df)), index=price_df.index),
                'fear_greed': pd.Series(np.random.randint(0, 100, len(price_df)), index=price_df.index)
            }
        
        # Train pipeline
        results = ml_pipeline.train_pipeline(
            price_data=price_df,
            market_indicators=market_indicators,
            save_models=save_models
        )
        
        logger.info(f"ML training completed: {results}")
        
    except Exception as e:
        logger.error(f"Background ML training failed: {e}", exc_info=True)

@router.get("/predict", response_model=PredictionResponse)
async def get_predictions(
    source: str = Query("cointracking"),
    min_usd: float = Query(100),
    lookback_days: int = Query(365, description="Days of price history for features")
):
    """
    Get ML predictions for market regime and asset returns
    """
    
    try:
        # Get current portfolio
        balances_response = await get_current_balances(source=source)
        if not balances_response.get("items"):
            raise HTTPException(status_code=400, detail="No portfolio data found")
        
        # Get top assets by value, filter by min_usd
        filtered_assets = [item for item in balances_response["items"] if item["value_usd"] >= min_usd]
        top_assets = sorted(
            filtered_assets,
            key=lambda x: x["value_usd"],
            reverse=True
        )[:10]  # Top 10 assets
        
        asset_symbols = [item["symbol"] for item in top_assets]
        
        # Collect price data
        price_data = {}
        for symbol in asset_symbols:
            try:
                prices = get_cached_history(symbol, days=lookback_days)
                if prices and len(prices) > 30:
                    price_data[symbol] = prices
            except Exception as e:
                logger.warning(f"Could not get price data for {symbol}: {e}")
                continue
        
        if len(price_data) < 2:
            raise HTTPException(
                status_code=400,
                detail="Insufficient price data for predictions"
            )
        
        # Create DataFrame
        price_df = pd.DataFrame(price_data).fillna(method='ffill').dropna()
        
        # Get predictions
        predictions = ml_pipeline.get_predictions(price_df)
        
        model_status = {
            "models_loaded": ml_pipeline.is_trained,
            "assets_analyzed": len(price_data),
            "data_points": len(price_df),
            "lookback_period": f"{lookback_days} days"
        }
        
        return PredictionResponse(
            success=True,
            regime_prediction=predictions.get('regime'),
            return_predictions=predictions.get('returns'),
            model_status=model_status,
            timestamp=pd.Timestamp.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ML prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.get("/regime/current")
async def get_current_regime(
    source: str = Query("cointracking"),
    min_usd: float = Query(100)
):
    """
    Get current market regime prediction only
    """
    
    try:
        # This is a simplified version focusing only on regime
        predictions = await get_predictions(source=source, min_usd=min_usd)
        
        if predictions.regime_prediction:
            regime_data = predictions.regime_prediction
            
            # Add interpretation
            regime = regime_data.get('regime', 'unknown')
            confidence = regime_data.get('confidence', 0)
            
            interpretations = {
                'accumulation': {
                    'description': 'Market in accumulation phase - good time to build positions',
                    'strategy': 'Increase allocation to quality assets',
                    'risk_level': 'moderate'
                },
                'expansion': {
                    'description': 'Market expanding - balanced growth phase',
                    'strategy': 'Maintain balanced allocation',
                    'risk_level': 'moderate'
                },
                'euphoria': {
                    'description': 'Market euphoria - high risk of correction',
                    'strategy': 'Consider taking profits, reduce risk',
                    'risk_level': 'high'
                },
                'distribution': {
                    'description': 'Market distribution phase - prepare for downturn',
                    'strategy': 'Increase stablecoin allocation',
                    'risk_level': 'high'
                }
            }
            
            interpretation = interpretations.get(regime, {
                'description': 'Regime unknown',
                'strategy': 'Maintain current allocation',
                'risk_level': 'unknown'
            })
            
            return {
                "success": True,
                "regime": regime,
                "confidence": confidence,
                "interpretation": interpretation,
                "probabilities": regime_data.get('probabilities', {}),
                "timestamp": regime_data.get('timestamp')
            }
        else:
            return {
                "success": False,
                "error": "Could not determine market regime",
                "fallback_regime": "expansion",  # Conservative default
                "confidence": 0.0
            }
            
    except Exception as e:
        logger.error(f"Failed to get regime: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "fallback_regime": "expansion",
            "confidence": 0.0
        }

@router.get("/models/status")
async def get_models_status():
    """
    Get ML models training and loading status
    """
    
    from pathlib import Path
    
    models_path = Path("data/models")
    
    status = {
        "models_directory_exists": models_path.exists(),
        "pipeline_trained": ml_pipeline.is_trained,
        "available_models": []
    }
    
    if models_path.exists():
        model_files = list(models_path.glob("*.pkl"))
        status["available_models"] = [f.name for f in model_files]
        status["models_count"] = len(model_files)
        
        # Check specific models
        status["regime_model_exists"] = (models_path / "regime_model.pkl").exists()
        status["return_models_exist"] = (models_path / "return_models.pkl").exists()
        status["feature_scaler_exists"] = (models_path / "feature_scaler.pkl").exists()
    
    # Try to load models if not already loaded
    if not ml_pipeline.is_trained:
        try:
            loaded = ml_pipeline.predictor.load_models()
            status["load_attempted"] = True
            status["load_successful"] = loaded
            if loaded:
                ml_pipeline.is_trained = True
        except Exception as e:
            status["load_error"] = str(e)
    
    return status

@router.delete("/models/clear")
async def clear_models():
    """
    Clear trained models from memory and disk
    """
    
    try:
        from pathlib import Path
        import shutil
        
        # Clear from memory
        ml_pipeline.predictor.regime_model = None
        ml_pipeline.predictor.return_models = {}
        ml_pipeline.is_trained = False
        
        # Clear from disk
        models_path = Path("data/models")
        if models_path.exists():
            shutil.rmtree(models_path)
            models_path.mkdir(parents=True, exist_ok=True)
        
        return {
            "success": True,
            "message": "Models cleared from memory and disk"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear models: {str(e)}")

@router.get("/features/importance")
async def get_feature_importance():
    """
    Get feature importance from trained models
    """
    
    try:
        if not ml_pipeline.is_trained:
            if not ml_pipeline.predictor.load_models():
                raise HTTPException(status_code=400, detail="No trained models available")
        
        importance_data = {}
        
        # Regime model feature importance
        if ml_pipeline.predictor.regime_model is not None:
            regime_importance = dict(zip(
                ml_pipeline.predictor.regime_model.feature_names_in_ if hasattr(ml_pipeline.predictor.regime_model, 'feature_names_in_') else range(len(ml_pipeline.predictor.regime_model.feature_importances_)),
                ml_pipeline.predictor.regime_model.feature_importances_
            ))
            
            # Sort by importance
            regime_importance = dict(sorted(
                regime_importance.items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            importance_data['regime_model'] = {
                'features': regime_importance,
                'top_5_features': list(regime_importance.keys())[:5]
            }
        
        # Return models feature importance (simplified)
        if ml_pipeline.predictor.return_models:
            return_importance = {}
            for asset, model in ml_pipeline.predictor.return_models.items():
                if hasattr(model, 'feature_importances_'):
                    feature_names = getattr(model, 'feature_names_in_', range(len(model.feature_importances_)))
                    asset_importance = dict(zip(feature_names, model.feature_importances_))
                    return_importance[asset] = dict(sorted(
                        asset_importance.items(),
                        key=lambda x: x[1],
                        reverse=True
                    ))
            
            importance_data['return_models'] = return_importance
        
        return {
            "success": True,
            "feature_importance": importance_data,
            "models_analyzed": len(importance_data)
        }
        
    except Exception as e:
        logger.error(f"Failed to get feature importance: {e}")
        raise HTTPException(status_code=500, detail=str(e))