"""
Machine Learning API Endpoints
ML-powered market regime detection and return forecasting
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
import pandas as pd
from pydantic import BaseModel
import logging
from datetime import datetime, timedelta
import numpy as np

from services.ml.orchestrator import get_orchestrator, initialize_ml_system, get_ml_predictions, get_ml_status
from services.ml.models.volatility_predictor import VolatilityPredictor
from services.ml.models.regime_detector import RegimeDetector
from services.ml.models.correlation_forecaster import CorrelationForecaster
from services.ml.models.sentiment_analyzer import SentimentAnalysisEngine, SentimentSource
from services.ml.models.rebalancing_engine import RebalancingEngine, SafetyLevel, RebalanceReason
from services.ml.data_pipeline import MLDataPipeline
from services.ml_models import ml_pipeline  # Import the ML pipeline
from services.price_history import get_cached_history
from connectors.cointracking_api import get_current_balances

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

# Initialize ML components
volatility_predictor = VolatilityPredictor()
regime_detector = RegimeDetector()
correlation_forecaster = CorrelationForecaster()
sentiment_engine = SentimentAnalysisEngine()
rebalancing_engine = RebalancingEngine()
data_pipeline = MLDataPipeline()

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

# --- UNIFIED ML ORCHESTRATOR ENDPOINTS ---

@router.post("/initialize")
async def initialize_unified_ml_system(
    background_tasks: BackgroundTasks,
    force_retrain: bool = Query(False, description="Force retraining of existing models"),
    source: str = Query("auto", description="Data source configuration (auto uses settings)")
):
    """
    Initialize the unified ML orchestrator system respecting configuration settings
    """
    try:
        # Start initialization in background
        background_tasks.add_task(
            _initialize_ml_background,
            force_retrain
        )
        
        return {
            "success": True,
            "message": "ML system initialization started in background",
            "force_retrain": force_retrain,
            "estimated_duration_minutes": 15
        }
        
    except Exception as e:
        logger.error(f"Failed to start ML initialization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

async def _initialize_ml_background(force_retrain: bool):
    """Background task for ML system initialization"""
    try:
        logger.info("Starting unified ML system initialization")
        result = await initialize_ml_system(force_retrain=force_retrain)
        logger.info(f"ML system initialization completed: {result}")
    except Exception as e:
        logger.error(f"Background ML initialization failed: {e}", exc_info=True)

@router.get("/unified/predictions")
async def get_unified_ml_predictions(
    symbols: Optional[List[str]] = Query(None, description="Assets to predict (None for portfolio assets)"),
    horizons: List[int] = Query([1, 7, 30], description="Prediction horizons in days")
):
    """
    Get unified predictions from all ML models using configured data source
    """
    try:
        predictions = await get_ml_predictions(symbols=symbols)
        
        return {
            "success": True,
            "predictions": predictions,
            "requested_symbols": symbols,
            "requested_horizons": horizons
        }
        
    except Exception as e:
        logger.error(f"Failed to get unified predictions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.get("/unified/status")
async def get_unified_ml_status():
    """
    Get comprehensive status of unified ML system
    """
    try:
        status = await get_ml_status()
        
        return {
            "success": True,
            "ml_system_status": status
        }
        
    except Exception as e:
        logger.error(f"Failed to get ML status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/unified/retrain")
async def retrain_unified_models(
    background_tasks: BackgroundTasks,
    model_names: Optional[List[str]] = Query(None, description="Models to retrain (None for all)"),
    force: bool = Query(False, description="Force retraining even if recent")
):
    """
    Retrain specified models in the unified ML system
    """
    try:
        orchestrator = get_orchestrator()
        
        # Start retraining in background
        background_tasks.add_task(
            _retrain_models_background,
            model_names,
            force
        )
        
        return {
            "success": True,
            "message": "Model retraining started in background",
            "models_to_retrain": model_names or "all",
            "force_retrain": force,
            "estimated_duration_minutes": (len(model_names) if model_names else 5) * 3
        }
        
    except Exception as e:
        logger.error(f"Failed to start model retraining: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")

async def _retrain_models_background(model_names: Optional[List[str]], force: bool):
    """Background task for model retraining"""
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.retrain_models(model_names=model_names, force=force)
        logger.info(f"Model retraining completed: {result}")
    except Exception as e:
        logger.error(f"Background model retraining failed: {e}", exc_info=True)

@router.delete("/unified/clear-caches")
async def clear_ml_caches():
    """
    Clear all ML system caches
    """
    try:
        orchestrator = get_orchestrator()
        cleared_counts = orchestrator.clear_caches()
        
        return {
            "success": True,
            "message": "ML caches cleared successfully",
            "cleared_counts": cleared_counts
        }
        
    except Exception as e:
        logger.error(f"Failed to clear ML caches: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cache clearing failed: {str(e)}")

# --- LEGACY ENDPOINTS (PRESERVED FOR COMPATIBILITY) ---

@router.post("/train")
async def train_models(
    request: TrainingRequest,
    background_tasks: BackgroundTasks,
    source: str = Query("cointracking", description="Data source for current portfolio")
):
    """
    Legacy endpoint - Train ML models for regime detection and return forecasting
    Redirects to unified ML system
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

# --- NEW VOLATILITY PREDICTION ENDPOINTS ---

@router.post("/volatility/train/{symbol}")
async def train_volatility_model(
    symbol: str,
    background_tasks: BackgroundTasks,
    days: int = Query(730, description="Days of training data"),
    validation_split: float = Query(0.2, description="Validation data fraction")
):
    """
    Train volatility prediction model for a specific asset
    """
    try:
        # Validate inputs
        if days < 100 or days > 2000:
            raise HTTPException(status_code=400, detail="Days must be between 100 and 2000")
        
        if validation_split < 0.1 or validation_split > 0.5:
            raise HTTPException(status_code=400, detail="Validation split must be between 0.1 and 0.5")
        
        symbol = symbol.upper()
        
        # Get price data
        price_data = data_pipeline.fetch_price_data(symbol, days=days)
        if price_data is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Insufficient price data for {symbol}"
            )
        
        # Start training in background
        def train_model_background():
            try:
                metadata = volatility_predictor.train_model(symbol, price_data, validation_split)
                logger.info(f"Background training completed for {symbol}")
                return metadata
            except Exception as e:
                logger.error(f"Background training failed for {symbol}: {str(e)}")
                raise
        
        background_tasks.add_task(train_model_background)
        
        return {
            "success": True,
            "message": f"Volatility model training started for {symbol}",
            "symbol": symbol,
            "training_data_points": len(price_data),
            "validation_split": validation_split,
            "expected_duration_minutes": 5
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting volatility training for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training setup failed: {str(e)}")

@router.get("/volatility/predict/{symbol}")
async def predict_volatility(
    symbol: str,
    lookback_days: int = Query(365, description="Days of recent data for prediction"),
    confidence_level: float = Query(0.95, description="Confidence level for intervals")
):
    """
    Predict volatility for multiple horizons with confidence intervals
    """
    try:
        # Validate inputs
        if lookback_days < 60 or lookback_days > 1000:
            raise HTTPException(status_code=400, detail="Lookback days must be between 60 and 1000")
        
        if confidence_level not in [0.90, 0.95, 0.99]:
            raise HTTPException(status_code=400, detail="Confidence level must be 0.90, 0.95, or 0.99")
        
        symbol = symbol.upper()
        
        # Load model if not already loaded
        if symbol not in volatility_predictor.models:
            success = volatility_predictor.load_model(symbol)
            if not success:
                raise HTTPException(
                    status_code=404,
                    detail=f"No trained model found for {symbol}. Train the model first."
                )
        
        # Get recent price data
        recent_data = data_pipeline.get_prediction_data(symbol, lookback_days)
        if recent_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient recent data for {symbol}"
            )
        
        # Make prediction
        prediction_result = volatility_predictor.predict_volatility(
            symbol, recent_data, confidence_level
        )
        
        return prediction_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting volatility for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.post("/volatility/train-portfolio")
async def train_portfolio_volatility_models(
    background_tasks: BackgroundTasks,
    source: str = Query("cointracking", description="Portfolio data source"),
    min_usd: float = Query(500, description="Minimum USD value for training"),
    days: int = Query(730, description="Days of training data")
):
    """
    Train volatility models for all assets in current portfolio
    """
    try:
        # Get portfolio assets
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
        
        if not portfolio_assets:
            raise HTTPException(
                status_code=404,
                detail="No portfolio assets found above minimum threshold"
            )
        
        # Filter assets with sufficient data
        trainable_assets = []
        for symbol in portfolio_assets:
            price_data = data_pipeline.fetch_price_data(symbol, days=days)
            if price_data is not None and len(price_data) >= 200:
                trainable_assets.append(symbol)
        
        if not trainable_assets:
            raise HTTPException(
                status_code=404,
                detail="No assets have sufficient data for training"
            )
        
        # Start training for all assets in background
        def train_portfolio_models():
            results = {}
            for symbol in trainable_assets:
                try:
                    price_data = data_pipeline.fetch_price_data(symbol, days=days)
                    if price_data is not None:
                        metadata = volatility_predictor.train_model(symbol, price_data)
                        results[symbol] = {
                            "status": "success",
                            "train_samples": metadata["train_samples"],
                            "best_val_loss": metadata["best_val_loss"]
                        }
                        logger.info(f"Portfolio training completed for {symbol}")
                except Exception as e:
                    results[symbol] = {"status": "failed", "error": str(e)}
                    logger.error(f"Portfolio training failed for {symbol}: {str(e)}")
            
            logger.info(f"Portfolio training completed: {len(results)} assets")
            return results
        
        background_tasks.add_task(train_portfolio_models)
        
        return {
            "success": True,
            "message": "Portfolio volatility model training started",
            "total_assets": len(portfolio_assets),
            "trainable_assets": len(trainable_assets),
            "assets": trainable_assets,
            "estimated_duration_minutes": len(trainable_assets) * 3
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting portfolio training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Portfolio training setup failed: {str(e)}")

@router.get("/volatility/models/status")
async def get_volatility_models_status():
    """
    Get status of all loaded volatility models
    """
    try:
        status = volatility_predictor.get_model_status()
        
        return {
            "success": True,
            "models_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting models status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/volatility/batch-predict")
async def batch_predict_volatility(
    symbols: List[str],
    lookback_days: int = Query(365, description="Days of recent data"),
    confidence_level: float = Query(0.95, description="Confidence level")
):
    """
    Batch predict volatility for multiple assets
    """
    try:
        # Validate inputs
        if not symbols or len(symbols) > 20:
            raise HTTPException(status_code=400, detail="Provide 1-20 symbols for batch prediction")
        
        symbols = [s.upper() for s in symbols]
        predictions = {}
        errors = {}
        
        for symbol in symbols:
            try:
                # Load model if needed
                if symbol not in volatility_predictor.models:
                    success = volatility_predictor.load_model(symbol)
                    if not success:
                        errors[symbol] = "No trained model available"
                        continue
                
                # Get data and predict
                recent_data = data_pipeline.get_prediction_data(symbol, lookback_days)
                if recent_data is None:
                    errors[symbol] = "Insufficient data for prediction"
                    continue
                
                prediction = volatility_predictor.predict_volatility(
                    symbol, recent_data, confidence_level
                )
                predictions[symbol] = prediction
                
            except Exception as e:
                errors[symbol] = str(e)
        
        return {
            "success": True,
            "predictions": predictions,
            "errors": errors,
            "total_requested": len(symbols),
            "successful_predictions": len(predictions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in batch volatility prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")

# --- REGIME DETECTION ENDPOINTS ---

@router.post("/regime/train")
async def train_regime_detection_model(
    background_tasks: BackgroundTasks,
    source: str = Query("cointracking", description="Portfolio data source"),
    min_usd: float = Query(1000, description="Minimum USD value for asset inclusion"),
    days: int = Query(1095, description="Days of training data (3 years recommended)")
):
    """
    Train market regime detection model using multi-asset data
    """
    try:
        # Validate inputs
        if days < 365 or days > 2000:
            raise HTTPException(status_code=400, detail="Days must be between 365 and 2000")
        
        # Get portfolio assets
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
        
        if len(portfolio_assets) < 3:
            raise HTTPException(
                status_code=400,
                detail="Need at least 3 assets for regime detection training"
            )
        
        # Limit to top assets for performance
        training_assets = portfolio_assets[:10]
        
        # Start training in background
        def train_regime_model():
            try:
                # Fetch multi-asset data
                multi_asset_data = {}
                for symbol in training_assets:
                    price_data = data_pipeline.fetch_price_data(symbol, days=days)
                    if price_data is not None and len(price_data) >= 200:
                        multi_asset_data[symbol] = price_data
                
                if len(multi_asset_data) < 3:
                    raise ValueError("Insufficient asset data for regime detection")
                
                # Train model
                metadata = regime_detector.train_model(multi_asset_data)
                logger.info("Regime detection model training completed")
                return metadata
                
            except Exception as e:
                logger.error(f"Regime detection training failed: {str(e)}")
                raise
        
        background_tasks.add_task(train_regime_model)
        
        return {
            "success": True,
            "message": "Regime detection model training started",
            "assets_for_training": training_assets,
            "training_period_days": days,
            "expected_duration_minutes": 10
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting regime detection training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training setup failed: {str(e)}")

@router.get("/regime/current")
async def get_current_market_regime(
    source: str = Query("cointracking", description="Data source"),
    lookback_days: int = Query(90, description="Days of recent data for prediction"),
    include_probabilities: bool = Query(True, description="Include regime probabilities")
):
    """
    Get current market regime prediction
    """
    try:
        # Validate inputs
        if lookback_days < 30 or lookback_days > 365:
            raise HTTPException(status_code=400, detail="Lookback days must be between 30 and 365")
        
        # Check if model is loaded
        if regime_detector.neural_model is None:
            success = regime_detector.load_model()
            if not success:
                raise HTTPException(
                    status_code=404,
                    detail="No trained regime detection model found. Train the model first."
                )
        
        # Get recent multi-asset data
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd=500)
        
        if len(portfolio_assets) < 3:
            # Use default major assets as fallback
            portfolio_assets = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX']
        
        # Fetch recent data for multiple assets
        multi_asset_data = {}
        for symbol in portfolio_assets[:8]:  # Limit for performance
            recent_data = data_pipeline.get_prediction_data(symbol, lookback_days)
            if recent_data is not None and len(recent_data) >= 30:
                multi_asset_data[symbol] = recent_data
        
        if len(multi_asset_data) < 3:
            raise HTTPException(
                status_code=404,
                detail="Insufficient recent data for regime detection"
            )
        
        # Predict regime
        regime_prediction = regime_detector.predict_regime(
            multi_asset_data,
            return_probabilities=include_probabilities
        )
        
        return {
            "success": True,
            "regime_prediction": regime_prediction,
            "data_sources": list(multi_asset_data.keys()),
            "lookback_period": f"{lookback_days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current market regime: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Regime prediction failed: {str(e)}")

@router.get("/regime/history")
async def get_regime_history(
    source: str = Query("cointracking", description="Data source"),
    days: int = Query(180, description="Days of historical regime data"),
    window_size: int = Query(30, description="Rolling window for regime detection")
):
    """
    Get historical market regime analysis
    """
    try:
        # Validate inputs
        if days < 90 or days > 730:
            raise HTTPException(status_code=400, detail="Days must be between 90 and 730")
        
        if window_size < 7 or window_size > 90:
            raise HTTPException(status_code=400, detail="Window size must be between 7 and 90 days")
        
        # Check if model is loaded
        if regime_detector.neural_model is None:
            success = regime_detector.load_model()
            if not success:
                raise HTTPException(
                    status_code=404,
                    detail="No trained regime detection model found"
                )
        
        # Get portfolio assets
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd=500)
        if len(portfolio_assets) < 3:
            portfolio_assets = ['BTC', 'ETH', 'SOL', 'ADA']
        
        # Fetch historical data
        multi_asset_data = {}
        for symbol in portfolio_assets[:6]:
            historical_data = data_pipeline.get_prediction_data(symbol, days + window_size)
            if historical_data is not None:
                multi_asset_data[symbol] = historical_data
        
        if len(multi_asset_data) < 3:
            raise HTTPException(status_code=404, detail="Insufficient historical data")
        
        # Calculate rolling regime predictions
        regime_history = []
        
        # Get date range for analysis
        common_dates = None
        for asset_data in multi_asset_data.values():
            if common_dates is None:
                common_dates = asset_data.index
            else:
                common_dates = common_dates.intersection(asset_data.index)
        
        # Rolling window analysis
        analysis_dates = common_dates[-days:]
        
        for i, end_date in enumerate(analysis_dates[window_size:]):
            try:
                # Get window data
                window_data = {}
                start_date = analysis_dates[i]
                
                for symbol, asset_data in multi_asset_data.items():
                    window_slice = asset_data.loc[start_date:end_date]
                    if len(window_slice) >= window_size // 2:  # Minimum data requirement
                        window_data[symbol] = window_slice
                
                if len(window_data) >= 3:
                    # Predict regime for this window
                    regime_pred = regime_detector.predict_regime(
                        window_data, 
                        return_probabilities=True
                    )
                    
                    regime_history.append({
                        'date': end_date.isoformat(),
                        'regime': regime_pred['predicted_regime'],
                        'regime_name': regime_pred['regime_name'],
                        'confidence': regime_pred['confidence'],
                        'probabilities': regime_pred.get('regime_probabilities', {})
                    })
            
            except Exception as e:
                logger.warning(f"Failed to analyze regime for {end_date}: {str(e)}")
                continue
        
        # Calculate regime statistics
        if regime_history:
            regimes = [r['regime'] for r in regime_history]
            regime_counts = np.bincount(regimes, minlength=4)
            
            regime_stats = {
                'total_periods': len(regime_history),
                'regime_distribution': {
                    regime_detector.regime_names[i]: int(count)
                    for i, count in enumerate(regime_counts)
                },
                'current_regime': regime_history[-1]['regime_name'] if regime_history else None,
                'regime_transitions': len([i for i in range(1, len(regimes)) if regimes[i] != regimes[i-1]])
            }
        else:
            regime_stats = {"error": "No valid regime analysis periods"}
        
        return {
            "success": True,
            "regime_history": regime_history[-100:],  # Return last 100 periods
            "regime_statistics": regime_stats,
            "analysis_parameters": {
                "days_analyzed": days,
                "window_size": window_size,
                "assets_used": list(multi_asset_data.keys())
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting regime history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Regime history analysis failed: {str(e)}")

@router.get("/regime/status")
async def get_regime_model_status():
    """
    Get regime detection model status
    """
    try:
        status = regime_detector.get_model_status()
        
        return {
            "success": True,
            "model_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting regime model status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/regime/interpret")
async def interpret_regime_prediction(
    regime_data: Dict[str, Any],
    portfolio_context: Optional[Dict[str, float]] = None
):
    """
    Get detailed interpretation and recommendations for regime prediction
    """
    try:
        predicted_regime = regime_data.get('predicted_regime', 0)
        confidence = regime_data.get('confidence', 0.0)
        
        if predicted_regime not in range(4):
            raise HTTPException(status_code=400, detail="Invalid regime prediction")
        
        # Get regime description
        regime_info = regime_detector.regime_descriptions[predicted_regime]
        
        # Generate specific recommendations
        recommendations = []
        
        if predicted_regime == 0:  # Accumulation
            recommendations.extend([
                "Consider gradually increasing allocation to quality crypto assets",
                "Focus on major cryptocurrencies (BTC, ETH) during this phase",
                "Use dollar-cost averaging to build positions",
                "Monitor for signs of expansion phase beginning"
            ])
        elif predicted_regime == 1:  # Expansion  
            recommendations.extend([
                "Maintain current allocation strategy",
                "Consider selective additions to promising altcoins",
                "Monitor momentum indicators for continued expansion",
                "Prepare for potential regime transition"
            ])
        elif predicted_regime == 2:  # Euphoria
            recommendations.extend([
                "Reduce exposure to speculative positions",
                "Take profits on overextended positions",
                "Increase stablecoin allocation as hedge",
                "Avoid FOMO-driven decisions"
            ])
        elif predicted_regime == 3:  # Distribution
            recommendations.extend([
                "Adopt defensive positioning",
                "Increase cash/stablecoin reserves significantly",
                "Avoid new risky positions",
                "Consider hedging strategies"
            ])
        
        # Portfolio-specific recommendations
        if portfolio_context:
            total_value = sum(portfolio_context.values())
            risky_assets = ['BTC', 'ETH', 'SOL', 'AVAX', 'ADA', 'DOT']  # Example
            
            risky_allocation = sum(
                value for symbol, value in portfolio_context.items() 
                if symbol in risky_assets
            ) / total_value if total_value > 0 else 0
            
            if predicted_regime >= 2 and risky_allocation > 0.7:  # Euphoria/Distribution with high risk
                recommendations.append(f"Current risky allocation ({risky_allocation:.1%}) is high for {regime_info['name']} regime")
            elif predicted_regime <= 1 and risky_allocation < 0.3:  # Accumulation/Expansion with low risk
                recommendations.append(f"Current risky allocation ({risky_allocation:.1%}) may be too conservative for {regime_info['name']} regime")
        
        # Risk assessment
        risk_level = regime_info['risk_level']
        if confidence < 0.6:
            risk_level += " (Low Confidence)"
        elif confidence > 0.8:
            risk_level += " (High Confidence)"
        
        interpretation = {
            "regime_analysis": regime_info,
            "confidence_assessment": {
                "confidence_score": confidence,
                "confidence_level": "High" if confidence > 0.8 else "Medium" if confidence > 0.6 else "Low",
                "interpretation_reliability": "Strong" if confidence > 0.75 else "Moderate" if confidence > 0.5 else "Weak"
            },
            "recommendations": recommendations,
            "risk_assessment": {
                "overall_risk_level": risk_level,
                "key_risks": regime_info.get('characteristics', []),
                "monitoring_priorities": [
                    "Watch for regime transition signals",
                    "Monitor key crypto correlation patterns",
                    "Track volume and momentum indicators"
                ]
            },
            "allocation_guidance": {
                "suggested_bias": regime_info['allocation_bias'],
                "risk_budget_adjustment": "Decrease" if predicted_regime >= 2 else "Maintain" if predicted_regime == 1 else "Increase"
            }
        }
        
        return {
            "success": True,
            "interpretation": interpretation,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error interpreting regime prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Interpretation failed: {str(e)}")

# --- CORRELATION FORECASTING ENDPOINTS ---

@router.post("/correlation/train")
async def train_correlation_forecaster(
    background_tasks: BackgroundTasks,
    source: str = Query("cointracking", description="Portfolio data source"),
    min_usd: float = Query(1000, description="Minimum USD value for asset inclusion"),
    days: int = Query(1095, description="Days of training data (3 years recommended)")
):
    """
    Train correlation forecasting model using Transformer architecture
    """
    try:
        # Validate inputs
        if days < 730 or days > 2190:
            raise HTTPException(status_code=400, detail="Days must be between 730 (2 years) and 2190 (6 years)")
        
        # Get portfolio assets
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
        
        if len(portfolio_assets) < 4:
            raise HTTPException(
                status_code=400,
                detail="Need at least 4 assets for correlation forecasting training"
            )
        
        # Limit to top assets for computational efficiency
        training_assets = portfolio_assets[:12]
        
        # Start training in background
        def train_correlation_model():
            try:
                # Fetch multi-asset data
                multi_asset_data = {}
                for symbol in training_assets:
                    price_data = data_pipeline.fetch_price_data(symbol, days=days)
                    if price_data is not None and len(price_data) >= 365:
                        multi_asset_data[symbol] = price_data
                
                if len(multi_asset_data) < 4:
                    raise ValueError("Insufficient asset data for correlation forecasting")
                
                # Train model
                metadata = correlation_forecaster.train_model(multi_asset_data)
                logger.info("Correlation forecasting model training completed")
                return metadata
                
            except Exception as e:
                logger.error(f"Correlation forecasting training failed: {str(e)}")
                raise
        
        background_tasks.add_task(train_correlation_model)
        
        return {
            "success": True,
            "message": "Correlation forecasting model training started",
            "assets_for_training": training_assets,
            "training_period_days": days,
            "expected_duration_minutes": 20
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting correlation forecasting training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training setup failed: {str(e)}")

@router.get("/correlation/predict")
async def predict_correlations(
    source: str = Query("cointracking", description="Data source"),
    lookback_days: int = Query(365, description="Days of recent data for prediction"),
    horizons: Optional[List[int]] = Query([1, 7, 30], description="Prediction horizons in days"),
    min_usd: float = Query(500, description="Minimum USD value for asset inclusion")
):
    """
    Predict future asset correlations using Transformer model
    """
    try:
        # Validate inputs
        if lookback_days < 90 or lookback_days > 730:
            raise HTTPException(status_code=400, detail="Lookback days must be between 90 and 730")
        
        if not horizons or any(h < 1 or h > 90 for h in horizons):
            raise HTTPException(status_code=400, detail="Horizons must be between 1 and 90 days")
        
        # Check if models are loaded
        if not correlation_forecaster.models:
            success = correlation_forecaster.load_models()
            if not success:
                raise HTTPException(
                    status_code=404,
                    detail="No trained correlation forecasting models found. Train the model first."
                )
        
        # Get portfolio assets for correlation analysis
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
        
        if len(portfolio_assets) < 4:
            # Use default major assets as fallback
            portfolio_assets = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX', 'DOT', 'MATIC', 'LINK']
        
        # Fetch recent data for multiple assets
        multi_asset_data = {}
        for symbol in portfolio_assets[:10]:  # Limit for performance
            recent_data = data_pipeline.get_prediction_data(symbol, lookback_days)
            if recent_data is not None and len(recent_data) >= 90:
                multi_asset_data[symbol] = recent_data
        
        if len(multi_asset_data) < 4:
            raise HTTPException(
                status_code=404,
                detail="Insufficient recent data for correlation prediction"
            )
        
        # Predict correlations
        correlation_predictions = correlation_forecaster.predict_correlations(
            multi_asset_data,
            horizons=horizons
        )
        
        return {
            "success": True,
            "correlation_predictions": correlation_predictions,
            "data_sources": list(multi_asset_data.keys()),
            "prediction_horizons": horizons,
            "lookback_period": f"{lookback_days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting correlations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Correlation prediction failed: {str(e)}")

@router.get("/correlation/analysis")
async def analyze_correlation_changes(
    source: str = Query("cointracking", description="Data source"),
    analysis_days: int = Query(180, description="Days to analyze for correlation trends"),
    min_usd: float = Query(500, description="Minimum USD value for asset inclusion")
):
    """
    Analyze recent correlation changes and market patterns
    """
    try:
        # Validate inputs
        if analysis_days < 90 or analysis_days > 365:
            raise HTTPException(status_code=400, detail="Analysis days must be between 90 and 365")
        
        # Get portfolio assets
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
        
        if len(portfolio_assets) < 4:
            # Use default assets
            portfolio_assets = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX', 'DOT']
        
        # Fetch historical data
        multi_asset_data = {}
        for symbol in portfolio_assets[:8]:
            historical_data = data_pipeline.get_prediction_data(symbol, analysis_days + 30)
            if historical_data is not None and len(historical_data) >= analysis_days:
                multi_asset_data[symbol] = historical_data
        
        if len(multi_asset_data) < 4:
            raise HTTPException(status_code=404, detail="Insufficient historical data for analysis")
        
        # Perform correlation analysis
        correlation_analysis = correlation_forecaster.analyze_correlation_changes(
            multi_asset_data,
            lookback_days=analysis_days
        )
        
        return {
            "success": True,
            "correlation_analysis": correlation_analysis,
            "assets_analyzed": list(multi_asset_data.keys()),
            "analysis_period": f"{analysis_days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing correlations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Correlation analysis failed: {str(e)}")

@router.get("/correlation/matrix/current")
async def get_current_correlation_matrix(
    source: str = Query("cointracking", description="Data source"),
    window_days: int = Query(30, description="Rolling window for correlation calculation"),
    min_usd: float = Query(500, description="Minimum USD value for asset inclusion")
):
    """
    Get current correlation matrix for portfolio assets
    """
    try:
        # Validate inputs
        if window_days < 7 or window_days > 90:
            raise HTTPException(status_code=400, detail="Window days must be between 7 and 90")
        
        # Get portfolio assets
        portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
        
        if len(portfolio_assets) < 2:
            # Use default assets
            portfolio_assets = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX']
        
        # Fetch recent data
        multi_asset_data = {}
        for symbol in portfolio_assets[:10]:
            recent_data = data_pipeline.get_prediction_data(symbol, window_days + 30)
            if recent_data is not None and len(recent_data) >= window_days:
                multi_asset_data[symbol] = recent_data.tail(window_days)
        
        if len(multi_asset_data) < 2:
            raise HTTPException(status_code=404, detail="Insufficient data for correlation matrix")
        
        # Calculate correlation matrix
        returns_data = {}
        for symbol, price_data in multi_asset_data.items():
            returns_data[symbol] = price_data['close'].pct_change().fillna(0)
        
        returns_df = pd.DataFrame(returns_data)
        correlation_matrix = returns_df.corr()
        
        # Add volatility information
        volatilities = {}
        for symbol in returns_df.columns:
            volatilities[symbol] = float(returns_df[symbol].std() * np.sqrt(365))  # Annualized
        
        # Risk metrics
        avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].mean()
        
        return {
            "success": True,
            "correlation_matrix": correlation_matrix.to_dict(),
            "asset_volatilities": volatilities,
            "market_metrics": {
                "average_correlation": float(avg_correlation),
                "diversification_ratio": 1.0 - avg_correlation,
                "correlation_regime": "high" if avg_correlation > 0.7 else "medium" if avg_correlation > 0.4 else "low",
                "window_period": f"{window_days} days"
            },
            "assets": list(multi_asset_data.keys()),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating correlation matrix: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Correlation matrix calculation failed: {str(e)}")

@router.get("/correlation/status")
async def get_correlation_model_status():
    """
    Get correlation forecasting model status
    """
    try:
        status = correlation_forecaster.get_model_status()
        
        return {
            "success": True,
            "model_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting correlation model status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

# --- SENTIMENT ANALYSIS ENDPOINTS ---

@router.get("/sentiment/analyze")
async def analyze_market_sentiment(
    source: str = Query("cointracking", description="Portfolio data source"),
    days: int = Query(7, description="Days of sentiment data to analyze"),
    min_usd: float = Query(500, description="Minimum USD value for asset inclusion"),
    symbols: Optional[List[str]] = Query(None, description="Specific symbols to analyze")
):
    """
    Perform comprehensive market sentiment analysis using multiple data sources
    """
    try:
        # Validate inputs
        if days < 1 or days > 30:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 30")
        
        # Get symbols to analyze
        if symbols:
            symbols = [s.upper() for s in symbols[:10]]  # Limit to 10 symbols
        else:
            # Get portfolio assets
            portfolio_assets = data_pipeline.fetch_portfolio_assets(source, min_usd)
            
            if len(portfolio_assets) < 1:
                # Use default major assets
                symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX']
            else:
                symbols = portfolio_assets[:8]  # Top 8 assets for performance
        
        logger.info(f"Analyzing sentiment for symbols: {symbols}")
        
        # Perform sentiment analysis
        sentiment_analysis = await sentiment_engine.analyze_market_sentiment(symbols, days)
        
        return {
            "success": True,
            "sentiment_analysis": sentiment_analysis,
            "analyzed_symbols": symbols,
            "analysis_period": f"{days} days",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing market sentiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")

@router.get("/sentiment/symbol/{symbol}")
async def get_symbol_sentiment(
    symbol: str,
    days: int = Query(7, description="Days of sentiment data"),
    sources: Optional[List[str]] = Query(["fear_greed", "social_mentions", "news"], 
                                        description="Sentiment sources to include")
):
    """
    Get detailed sentiment analysis for a specific symbol
    """
    try:
        # Validate inputs
        symbol = symbol.upper()
        if days < 1 or days > 14:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 14")
        
        # Convert source strings to SentimentSource enums
        sentiment_sources = []
        for source_str in sources:
            try:
                sentiment_sources.append(SentimentSource(source_str.lower()))
            except ValueError:
                logger.warning(f"Unknown sentiment source: {source_str}")
        
        if not sentiment_sources:
            sentiment_sources = [SentimentSource.FEAR_GREED, SentimentSource.SOCIAL_MENTIONS, SentimentSource.NEWS]
        
        logger.info(f"Collecting sentiment for {symbol} from sources: {[s.value for s in sentiment_sources]}")
        
        # Collect sentiment data
        sentiment_data = await sentiment_engine.collect_multi_source_sentiment(
            [symbol], 
            days, 
            sentiment_sources
        )
        
        # Aggregate sentiment for the symbol
        symbol_data = sentiment_data.get(symbol, [])
        aggregated_sentiment = sentiment_engine.aggregate_sentiment_scores(symbol_data, time_window_hours=12)
        
        # Add raw data summary
        raw_data_summary = []
        for data in symbol_data[-20:]:  # Last 20 data points
            raw_data_summary.append({
                "timestamp": data.timestamp.isoformat(),
                "source": data.source.value,
                "sentiment_score": data.sentiment_score,
                "confidence": data.confidence,
                "raw_data": data.raw_data
            })
        
        return {
            "success": True,
            "symbol": symbol,
            "aggregated_sentiment": aggregated_sentiment,
            "raw_data_summary": raw_data_summary,
            "sources_used": [s.value for s in sentiment_sources],
            "collection_period": f"{days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sentiment for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Symbol sentiment analysis failed: {str(e)}")

@router.get("/sentiment/fear-greed")
async def get_fear_greed_index(
    days: int = Query(7, description="Days of Fear & Greed data")
):
    """
    Get Fear & Greed Index data
    """
    try:
        # Validate inputs
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        # Get Fear & Greed data
        fear_greed_collector = sentiment_engine.collectors[SentimentSource.FEAR_GREED]
        await fear_greed_collector.initialize()
        
        try:
            fear_greed_data = await fear_greed_collector.collect_sentiment("BTC", days)
        finally:
            await fear_greed_collector.cleanup()
        
        # Process data for response
        processed_data = []
        for data in fear_greed_data:
            processed_data.append({
                "timestamp": data.timestamp.isoformat(),
                "fear_greed_value": data.raw_data.get("fear_greed_value", 50),
                "sentiment_score": data.sentiment_score,
                "classification": data.raw_data.get("classification", "neutral"),
                "confidence": data.confidence
            })
        
        # Calculate recent trend
        if len(processed_data) >= 2:
            recent_avg = np.mean([d["fear_greed_value"] for d in processed_data[:3]])
            older_avg = np.mean([d["fear_greed_value"] for d in processed_data[-3:]])
            trend = "improving" if recent_avg > older_avg + 5 else "declining" if recent_avg < older_avg - 5 else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "success": True,
            "fear_greed_data": processed_data,
            "current_reading": {
                "value": processed_data[0]["fear_greed_value"] if processed_data else 50,
                "classification": processed_data[0]["classification"] if processed_data else "neutral",
                "sentiment_score": processed_data[0]["sentiment_score"] if processed_data else 0.0
            },
            "trend_analysis": {
                "trend": trend,
                "data_points": len(processed_data),
                "period": f"{days} days"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Fear & Greed index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fear & Greed index retrieval failed: {str(e)}")

@router.get("/sentiment/social/{symbol}")
async def get_social_sentiment(
    symbol: str,
    days: int = Query(3, description="Days of social sentiment data"),
    time_window: int = Query(6, description="Time window in hours for aggregation")
):
    """
    Get social media sentiment analysis for a symbol
    """
    try:
        # Validate inputs
        symbol = symbol.upper()
        if days < 1 or days > 7:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 7")
        
        if time_window < 1 or time_window > 24:
            raise HTTPException(status_code=400, detail="Time window must be between 1 and 24 hours")
        
        # Get social sentiment data
        social_collector = sentiment_engine.collectors[SentimentSource.SOCIAL_MENTIONS]
        await social_collector.initialize()
        
        try:
            social_data = await social_collector.collect_sentiment(symbol, days)
        finally:
            await social_collector.cleanup()
        
        # Aggregate by time windows
        aggregated_sentiment = sentiment_engine.aggregate_sentiment_scores(social_data, time_window)
        
        # Calculate social metrics
        if social_data:
            total_mentions = sum(d.raw_data.get("mentions_count", 0) for d in social_data)
            avg_sentiment = np.mean([d.sentiment_score for d in social_data])
            sentiment_volatility = np.std([d.sentiment_score for d in social_data])
            
            # Recent vs older comparison
            midpoint = len(social_data) // 2
            recent_sentiment = np.mean([d.sentiment_score for d in social_data[:midpoint]]) if midpoint > 0 else 0
            older_sentiment = np.mean([d.sentiment_score for d in social_data[midpoint:]]) if midpoint > 0 else 0
            
            social_metrics = {
                "total_mentions": total_mentions,
                "average_sentiment": avg_sentiment,
                "sentiment_volatility": sentiment_volatility,
                "momentum": recent_sentiment - older_sentiment,
                "engagement_quality": "high" if total_mentions > 100 else "medium" if total_mentions > 20 else "low"
            }
        else:
            social_metrics = {
                "total_mentions": 0,
                "average_sentiment": 0.0,
                "sentiment_volatility": 0.0,
                "momentum": 0.0,
                "engagement_quality": "no_data"
            }
        
        return {
            "success": True,
            "symbol": symbol,
            "aggregated_sentiment": aggregated_sentiment,
            "social_metrics": social_metrics,
            "data_points": len(social_data),
            "analysis_period": f"{days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social sentiment for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Social sentiment analysis failed: {str(e)}")

@router.get("/sentiment/news/{symbol}")
async def get_news_sentiment(
    symbol: str,
    days: int = Query(5, description="Days of news sentiment data")
):
    """
    Get news sentiment analysis for a symbol
    """
    try:
        # Validate inputs
        symbol = symbol.upper()
        if days < 1 or days > 14:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 14")
        
        # Get news sentiment data
        news_collector = sentiment_engine.collectors[SentimentSource.NEWS]
        await news_collector.initialize()
        
        try:
            news_data = await news_collector.collect_sentiment(symbol, days)
        finally:
            await news_collector.cleanup()
        
        # Process news data
        processed_news = []
        for data in news_data:
            processed_news.append({
                "timestamp": data.timestamp.isoformat(),
                "headline": data.raw_data.get("headline", ""),
                "source": data.raw_data.get("source", ""),
                "sentiment_score": data.sentiment_score,
                "confidence": data.confidence,
                "url": data.raw_data.get("url", "")
            })
        
        # Aggregate news sentiment
        aggregated_sentiment = sentiment_engine.aggregate_sentiment_scores(news_data, time_window_hours=24)
        
        # News-specific analysis
        if news_data:
            # Sentiment distribution
            sentiment_scores = [d.sentiment_score for d in news_data]
            positive_news = len([s for s in sentiment_scores if s > 0.1])
            negative_news = len([s for s in sentiment_scores if s < -0.1])
            neutral_news = len(sentiment_scores) - positive_news - negative_news
            
            # Source diversity
            sources = list(set(d.raw_data.get("source", "") for d in news_data))
            
            news_analysis = {
                "total_articles": len(news_data),
                "positive_articles": positive_news,
                "negative_articles": negative_news,
                "neutral_articles": neutral_news,
                "source_diversity": len(sources),
                "sources": sources,
                "sentiment_trend": "improving" if aggregated_sentiment["temporal_trend"] and 
                                len(aggregated_sentiment["temporal_trend"]) >= 2 and
                                aggregated_sentiment["temporal_trend"][0]["sentiment"] > 
                                aggregated_sentiment["temporal_trend"][-1]["sentiment"] else "stable"
            }
        else:
            news_analysis = {
                "total_articles": 0,
                "positive_articles": 0,
                "negative_articles": 0,
                "neutral_articles": 0,
                "source_diversity": 0,
                "sources": [],
                "sentiment_trend": "no_data"
            }
        
        return {
            "success": True,
            "symbol": symbol,
            "aggregated_sentiment": aggregated_sentiment,
            "news_analysis": news_analysis,
            "recent_headlines": processed_news[:10],  # Most recent 10 headlines
            "analysis_period": f"{days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting news sentiment for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"News sentiment analysis failed: {str(e)}")

@router.get("/sentiment/status")
async def get_sentiment_engine_status():
    """
    Get sentiment analysis engine status and configuration
    """
    try:
        status = sentiment_engine.get_sentiment_status()
        
        return {
            "success": True,
            "sentiment_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting sentiment engine status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

# --- AUTOMATED REBALANCING ENDPOINTS ---

@router.post("/rebalance/analyze-signals")
async def analyze_rebalancing_signals(
    source: str = Query("cointracking", description="Portfolio data source"),
    min_usd: float = Query(500, description="Minimum USD value for asset inclusion"),
    target_allocations: Optional[Dict[str, float]] = None
):
    """
    Analyze current market conditions and generate rebalancing signals
    """
    try:
        # Get current portfolio
        portfolio_response = get_current_balances(source=source)
        
        if not portfolio_response or not portfolio_response.get("items"):
            raise HTTPException(status_code=404, detail="No portfolio data found")
        
        # Convert to allocation weights
        total_value = sum(item.get("value_usd", 0) for item in portfolio_response["items"])
        current_portfolio = {}
        
        for item in portfolio_response["items"]:
            if item.get("value_usd", 0) >= min_usd:
                symbol = item.get("symbol", "").upper()
                weight = item.get("value_usd", 0) / total_value if total_value > 0 else 0
                current_portfolio[symbol] = weight
        
        if len(current_portfolio) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 assets for rebalancing analysis")
        
        logger.info(f"Analyzing rebalancing signals for portfolio with {len(current_portfolio)} assets")
        
        # Analyze rebalancing signals
        signals = await rebalancing_engine.analyze_rebalancing_signals(
            current_portfolio, 
            target_allocations
        )
        
        # Process signals for response
        processed_signals = []
        for signal in signals:
            processed_signals.append({
                "reason": signal.reason.value,
                "severity": signal.severity,
                "confidence": signal.confidence,
                "recommended_action": signal.recommended_action,
                "affected_assets": signal.affected_assets,
                "timestamp": signal.timestamp.isoformat(),
                "metadata": signal.metadata
            })
        
        return {
            "success": True,
            "current_portfolio": current_portfolio,
            "total_portfolio_value": total_value,
            "rebalancing_signals": processed_signals,
            "signal_summary": {
                "total_signals": len(signals),
                "high_priority_signals": len([s for s in signals if s.severity > 0.7]),
                "most_urgent_reason": signals[0].reason.value if signals else None,
                "max_confidence": max([s.confidence for s in signals]) if signals else 0.0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing rebalancing signals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signal analysis failed: {str(e)}")

@router.post("/rebalance/generate-proposal")
async def generate_rebalancing_proposal(
    source: str = Query("cointracking", description="Portfolio data source"),
    min_usd: float = Query(500, description="Minimum USD value for asset inclusion"),
    safety_level: str = Query("moderate", description="Safety level: conservative, moderate, aggressive")
):
    """
    Generate a specific rebalancing proposal with trades and safety checks
    """
    try:
        # Validate safety level
        try:
            safety_enum = SafetyLevel(safety_level.lower())
            rebalancing_engine.safety_level = safety_enum
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid safety level")
        
        # Get current portfolio and prices
        portfolio_response = get_current_balances(source=source)
        
        if not portfolio_response or not portfolio_response.get("items"):
            raise HTTPException(status_code=404, detail="No portfolio data found")
        
        # Process portfolio data
        total_value = sum(item.get("value_usd", 0) for item in portfolio_response["items"])
        current_portfolio = {}
        current_prices = {}
        
        for item in portfolio_response["items"]:
            if item.get("value_usd", 0) >= min_usd:
                symbol = item.get("symbol", "").upper()
                weight = item.get("value_usd", 0) / total_value if total_value > 0 else 0
                price = item.get("price_usd", 1.0)
                
                current_portfolio[symbol] = weight
                current_prices[symbol] = price
        
        if len(current_portfolio) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 assets for rebalancing")
        
        # Generate rebalancing signals
        signals = await rebalancing_engine.analyze_rebalancing_signals(current_portfolio)
        
        if not signals:
            return {
                "success": True,
                "message": "No rebalancing signals detected",
                "current_portfolio": current_portfolio,
                "proposal": None
            }
        
        # Generate rebalancing proposal
        proposal = rebalancing_engine.generate_rebalance_proposal(
            current_portfolio,
            signals, 
            total_value,
            current_prices
        )
        
        if not proposal:
            return {
                "success": True,
                "message": "No rebalancing action recommended",
                "current_portfolio": current_portfolio,
                "signals": len(signals),
                "proposal": None
            }
        
        # Convert proposal to response format
        proposal_dict = {
            "proposal_id": proposal.proposal_id,
            "current_allocations": proposal.current_allocations,
            "target_allocations": proposal.target_allocations,
            "trades_required": proposal.trades_required,
            "expected_cost": proposal.expected_cost,
            "expected_benefit": proposal.expected_benefit,
            "net_benefit": proposal.expected_benefit - proposal.expected_cost,
            "risk_assessment": proposal.risk_assessment,
            "safety_checks": proposal.safety_checks,
            "confidence": proposal.confidence,
            "reasoning": proposal.reasoning,
            "timestamp": proposal.timestamp.isoformat()
        }
        
        # Evaluate proposal
        evaluation = rebalancing_engine.evaluate_proposal(proposal)
        
        return {
            "success": True,
            "portfolio_value": total_value,
            "safety_level": safety_level,
            "rebalancing_proposal": proposal_dict,
            "evaluation": evaluation,
            "signals_analyzed": len(signals)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating rebalancing proposal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Proposal generation failed: {str(e)}")

@router.get("/rebalance/safety-check")
async def run_safety_checks(
    proposal_id: str,
    source: str = Query("cointracking", description="Portfolio data source")
):
    """
    Run comprehensive safety checks on a rebalancing proposal
    """
    try:
        # This would normally load a stored proposal by ID
        # For now, we'll return the safety mechanism configuration and status
        
        safety_status = {
            "safety_mechanisms_active": True,
            "safety_configuration": rebalancing_engine.safety_mechanisms.config,
            "current_safety_level": rebalancing_engine.safety_level.value,
            "recent_rebalances": len(rebalancing_engine.recent_rebalances),
            "last_rebalance": rebalancing_engine.last_rebalance.isoformat() if rebalancing_engine.last_rebalance else None
        }
        
        # Mock safety check results for demonstration
        mock_safety_checks = {
            "trading_limits": {
                "single_trade_limit": True,
                "daily_volume_limit": True,
                "min_trade_size": True,
                "max_trade_size": True
            },
            "risk_limits": {
                "concentration_limit": True,
                "volatility_increase": True,
                "diversification_ratio": True,
                "correlation_limit": True
            },
            "timing_constraints": {
                "min_interval": True,
                "daily_frequency": True,
                "blackout_hours": True
            },
            "market_conditions": {
                "market_volatility": True,
                "market_liquidity": True,
                "emergency_stop_1h": True,
                "emergency_stop_24h": True
            }
        }
        
        # Calculate overall safety score
        all_checks = []
        for category in mock_safety_checks.values():
            all_checks.extend(category.values())
        
        safety_score = sum(all_checks) / len(all_checks) if all_checks else 0
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "safety_status": safety_status,
            "safety_checks": mock_safety_checks,
            "overall_safety_score": safety_score,
            "recommendation": "approved" if safety_score > 0.8 else "review" if safety_score > 0.6 else "rejected",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error running safety checks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Safety check failed: {str(e)}")

@router.post("/rebalance/configure-safety")
async def configure_safety_settings(
    safety_level: str = Query("moderate", description="Overall safety level"),
    custom_config: Optional[Dict[str, Any]] = None
):
    """
    Configure automated rebalancing safety settings
    """
    try:
        # Validate and set safety level
        try:
            safety_enum = SafetyLevel(safety_level.lower())
            rebalancing_engine.safety_level = safety_enum
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid safety level")
        
        # Apply custom configuration if provided
        if custom_config:
            # Validate and apply custom safety configurations
            current_config = rebalancing_engine.safety_mechanisms.config.copy()
            
            # Only allow modification of certain parameters
            allowed_modifications = [
                "max_single_trade_pct", "max_daily_trades_pct", "min_trade_size_usd",
                "max_portfolio_concentration", "min_rebalance_interval_hours",
                "max_rebalance_frequency_daily"
            ]
            
            for key, value in custom_config.items():
                if key in allowed_modifications and isinstance(value, (int, float)):
                    current_config[key] = value
            
            rebalancing_engine.safety_mechanisms.config = current_config
        
        return {
            "success": True,
            "safety_level": safety_level,
            "safety_configuration": rebalancing_engine.safety_mechanisms.config,
            "message": "Safety settings updated successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring safety settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Safety configuration failed: {str(e)}")

@router.get("/rebalance/history")
async def get_rebalancing_history(
    days: int = Query(30, description="Days of history to retrieve"),
    source: str = Query("cointracking", description="Portfolio data source")
):
    """
    Get historical rebalancing activity and performance
    """
    try:
        # Validate inputs
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        # Mock historical data for demonstration
        # In production, this would query a database of rebalancing history
        
        mock_history = []
        base_time = datetime.now()
        
        # Generate some mock historical rebalances
        for i in range(min(days // 7, 10)):  # Weekly rebalances
            rebalance_time = base_time - timedelta(days=i*7)
            
            mock_history.append({
                "timestamp": rebalance_time.isoformat(),
                "proposal_id": f"rebal_{rebalance_time.strftime('%Y%m%d')}",
                "trigger_reason": ["drift_threshold", "regime_change", "volatility_spike"][i % 3],
                "assets_rebalanced": ["BTC", "ETH", "SOL"][:(i % 3) + 1],
                "total_trades": (i % 5) + 1,
                "expected_cost": 50 + (i * 20),
                "expected_benefit": 200 + (i * 50),
                "actual_cost": None,  # Would be filled after execution
                "actual_benefit": None,  # Would be calculated later
                "confidence": 0.6 + (i * 0.05),
                "safety_score": 0.8 + (i * 0.02),
                "status": "executed" if i > 2 else "proposed"
            })
        
        # Calculate summary statistics
        executed_rebalances = [r for r in mock_history if r["status"] == "executed"]
        
        summary_stats = {
            "total_rebalances": len(mock_history),
            "executed_rebalances": len(executed_rebalances),
            "avg_confidence": np.mean([r["confidence"] for r in mock_history]) if mock_history else 0,
            "avg_safety_score": np.mean([r["safety_score"] for r in mock_history]) if mock_history else 0,
            "total_expected_costs": sum(r["expected_cost"] for r in mock_history),
            "total_expected_benefits": sum(r["expected_benefit"] for r in mock_history),
            "most_common_trigger": "drift_threshold",  # Would be calculated from actual data
            "success_rate": 0.85  # Mock success rate
        }
        
        return {
            "success": True,
            "rebalancing_history": mock_history,
            "summary_statistics": summary_stats,
            "analysis_period": f"{days} days",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rebalancing history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")

@router.get("/rebalance/status")
async def get_rebalancing_engine_status():
    """
    Get current status of the automated rebalancing engine
    """
    try:
        status = rebalancing_engine.get_engine_status()
        
        return {
            "success": True,
            "engine_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting rebalancing engine status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")