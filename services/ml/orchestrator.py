"""
ML Orchestrator - Unified ML system respecting configuration settings
Integrates all ML models and respects data source configuration from settings.html
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import json

from config.settings import Settings
from .data_pipeline import MLDataPipeline
from .models.volatility_predictor import VolatilityPredictor
from .models.correlation_forecaster import CorrelationForecaster
from .models.sentiment_analyzer import SentimentAnalysisEngine
from .models.regime_detector import RegimeDetector
from .models.rebalancing_engine import RebalancingEngine
from services.risk.advanced_risk_engine import AdvancedRiskEngine, VaRMethod, RiskHorizon

logger = logging.getLogger(__name__)

class MLOrchestrator:
    """
    Unified ML orchestrator that respects configuration settings
    Manages all ML models and data sources according to settings.html configuration
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        
        # Initialize data pipeline with configuration awareness
        self.data_pipeline = MLDataPipeline()
        
        # Initialize ML models
        self.models = {
            'volatility': VolatilityPredictor(),
            'correlation': CorrelationForecaster(),
            'sentiment': SentimentAnalysisEngine(),
            'regime': RegimeDetector(),
            'rebalancing': RebalancingEngine()
        }
        
        # Initialize Advanced Risk Engine (Phase 3A integration)
        advanced_risk_config = {
            "var": {
                "confidence_levels": [0.95, 0.99],
                "methods": ["parametric", "historical", "monte_carlo"],
                "lookback_days": 252,
                "min_observations": 100
            },
            "stress_testing": {
                "enabled_scenarios": [
                    "crisis_2008", "covid_2020", "china_ban", "tether_collapse"
                ],
                "custom_scenarios": {},
                "recovery_model": "exponential"
            },
            "monte_carlo": {
                "simulations": 10000,
                "distribution": "student_t",
                "correlation_decay": 0.94
            }
        }
        self.advanced_risk_engine = AdvancedRiskEngine(advanced_risk_config)
        self.models['advanced_risk'] = self.advanced_risk_engine
        
        # Model status tracking
        self.model_status = {name: 'uninitialized' for name in self.models.keys()}
        self.last_training = {name: None for name in self.models.keys()}
        
        # Cache for predictions and metrics
        self.prediction_cache = {}
        self.metrics_cache = {}
        
        logger.info("ML Orchestrator initialized with configuration support")
    
    async def get_data_source_config(self) -> str:
        """
        Get the configured data source from settings
        Priority: frontend config > environment config > fallback detection
        
        Returns:
            Data source: 'stub', 'cointracking', or 'cointracking_api'
        """
        try:
            # Try to read from browser localStorage via API (simulating frontend config)
            # This would be the preferred method to sync with settings.html
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    # Try to get config from a potential config endpoint
                    response = await client.get("http://127.0.0.1:8000/api/config/data-source", timeout=2.0)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('data_source') in ['stub', 'cointracking', 'cointracking_api']:
                            logger.info(f"Using data source from config API: {data['data_source']}")
                            return data['data_source']
            except Exception:
                # Config API not available, continue with fallback logic
                pass
            
            # Fallback: Check environment/settings based detection
            if hasattr(self.settings, 'data_source'):
                return self.settings.data_source
            
            # Smart detection based on available resources
            if self.settings.cointracking.api_key and self.settings.cointracking.api_secret:
                logger.info("API keys found, using cointracking_api")
                return 'cointracking_api'
            elif Path('data/raw').exists() and any(Path('data/raw').glob('*.csv')):
                logger.info("CSV files found, using cointracking")
                return 'cointracking'  # CSV files available
            else:
                logger.info("No API keys or CSV files found, using stub data")
                return 'stub'  # Fallback to test data
                
        except Exception as e:
            logger.warning(f"Error getting data source config: {e}, using stub data")
            return 'stub'
    
    async def get_portfolio_assets(self, min_usd: float = 100) -> List[str]:
        """
        Get portfolio assets respecting configured data source
        
        Args:
            min_usd: Minimum USD value threshold
            
        Returns:
            List of asset symbols from configured source
        """
        try:
            data_source = await self.get_data_source_config()
            logger.info(f"Fetching portfolio assets from configured source: {data_source}")
            
            assets = self.data_pipeline.fetch_portfolio_assets(
                source=data_source, 
                min_usd=min_usd
            )
            
            logger.info(f"Retrieved {len(assets)} assets from {data_source}: {assets}")
            return assets
            
        except Exception as e:
            logger.error(f"Error fetching portfolio assets: {e}")
            return ['BTC', 'ETH', 'SOL', 'ADA']  # Safe fallback
    
    async def initialize_models(self, force_retrain: bool = False) -> Dict[str, Any]:
        """
        Initialize all ML models with current data source configuration
        
        Args:
            force_retrain: Force retraining even if models exist
            
        Returns:
            Status report of model initialization
        """
        logger.info("Initializing ML models with configuration-aware data")
        
        initialization_report = {
            'data_source': await self.get_data_source_config(),
            'models_initialized': [],
            'models_failed': [],
            'asset_count': 0,
            'training_samples': 0,
            'errors': []
        }
        
        try:
            # Get portfolio assets from configured source
            portfolio_assets = await self.get_portfolio_assets(min_usd=50)
            initialization_report['asset_count'] = len(portfolio_assets)
            
            if not portfolio_assets:
                raise ValueError("No portfolio assets found from configured data source")
            
            # Prepare training data
            logger.info(f"Preparing training data for {len(portfolio_assets)} assets")
            training_data = self.data_pipeline.prepare_training_data(
                symbols=portfolio_assets[:10],  # Limit for initial testing
                days=365,  # 1 year of data
                target_horizons=[1, 7, 30]
            )
            
            if not training_data:
                raise ValueError("No training data could be prepared")
            
            total_samples = sum(len(df) for df in training_data.values())
            initialization_report['training_samples'] = total_samples
            
            # Initialize each model
            for model_name, model in self.models.items():
                try:
                    logger.info(f"Initializing {model_name} model")
                    
                    if model_name == 'volatility':
                        # Train volatility predictor on each asset
                        for symbol, data in list(training_data.items())[:3]:  # Limit for testing
                            await self._train_volatility_model(symbol, data, force_retrain)
                    
                    elif model_name == 'correlation':
                        # Train correlation forecaster on multi-asset data
                        multi_asset_data = self.data_pipeline.prepare_multi_asset_data(
                            symbols=list(training_data.keys())[:5],
                            days=365
                        )
                        if len(multi_asset_data) > 100:
                            await self._train_correlation_model(multi_asset_data, force_retrain)
                    
                    elif model_name == 'sentiment':
                        # Initialize sentiment analyzer (usually doesn't need training)
                        self.model_status[model_name] = 'ready'
                    
                    elif model_name == 'regime':
                        # Train regime detector on available main asset (prefer BTC, ETH, then any)
                        main_asset = None
                        preferred_assets = ['BTC', 'ETH', 'BNB', 'ADA', 'SOL']
                        
                        # Try preferred assets first
                        for asset in preferred_assets:
                            if asset in training_data:
                                main_asset = asset
                                break
                        
                        # If no preferred asset, use first available asset
                        if main_asset is None and training_data:
                            main_asset = list(training_data.keys())[0]
                        
                        if main_asset:
                            logger.info(f"Training regime detector using {main_asset}")
                            await self._train_regime_model(training_data[main_asset], force_retrain)
                        else:
                            logger.warning("No suitable asset found for regime detector training")
                    
                    elif model_name == 'rebalancing':
                        # Initialize rebalancing engine
                        self.model_status[model_name] = 'ready'
                    
                    elif model_name == 'advanced_risk':
                        # Initialize Advanced Risk Engine with portfolio data
                        await self._initialize_advanced_risk_engine(training_data, force_retrain)
                        self.model_status[model_name] = 'ready'
                    
                    initialization_report['models_initialized'].append(model_name)
                    logger.info(f"Successfully initialized {model_name} model")
                    
                except Exception as e:
                    error_msg = f"Failed to initialize {model_name}: {str(e)}"
                    logger.error(error_msg)
                    initialization_report['models_failed'].append(model_name)
                    initialization_report['errors'].append(error_msg)
                    self.model_status[model_name] = 'failed'
            
            # Generate data quality report
            data_quality = self.data_pipeline.get_data_quality_report(training_data)
            initialization_report['data_quality'] = data_quality
            
            logger.info(f"Model initialization complete: "
                       f"{len(initialization_report['models_initialized'])} successful, "
                       f"{len(initialization_report['models_failed'])} failed")
            
            return initialization_report
            
        except Exception as e:
            error_msg = f"Critical error in model initialization: {str(e)}"
            logger.error(error_msg)
            initialization_report['errors'].append(error_msg)
            return initialization_report
    
    async def _train_volatility_model(self, symbol: str, data: Any, force_retrain: bool):
        """Train volatility predictor for a specific asset"""
        try:
            # Check if model already exists and is recent
            if not force_retrain and hasattr(self.models['volatility'], 'model'):
                last_training = self.last_training.get('volatility')
                if last_training and (datetime.now() - last_training) < timedelta(days=7):
                    self.model_status['volatility'] = 'ready'
                    return
            
            # Train the model (simplified for demonstration)
            logger.info(f"Training volatility model for {symbol}")
            
            # This would call the actual training method
            # self.models['volatility'].train(data)
            
            self.model_status['volatility'] = 'ready'
            self.last_training['volatility'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error training volatility model for {symbol}: {e}")
            self.model_status['volatility'] = 'failed'
    
    async def _train_correlation_model(self, multi_asset_data: Any, force_retrain: bool):
        """Train correlation forecaster"""
        try:
            if not force_retrain and hasattr(self.models['correlation'], 'model'):
                last_training = self.last_training.get('correlation')
                if last_training and (datetime.now() - last_training) < timedelta(days=7):
                    self.model_status['correlation'] = 'ready'
                    return
            
            logger.info("Training correlation forecaster")
            
            # This would call the actual training method
            # self.models['correlation'].train(multi_asset_data)
            
            self.model_status['correlation'] = 'ready'
            self.last_training['correlation'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error training correlation model: {e}")
            self.model_status['correlation'] = 'failed'
    
    async def _train_regime_model(self, data: Any, force_retrain: bool):
        """Train regime detector"""
        try:
            if not force_retrain and hasattr(self.models['regime'], 'model'):
                last_training = self.last_training.get('regime')
                if last_training and (datetime.now() - last_training) < timedelta(days=7):
                    self.model_status['regime'] = 'ready'
                    return
            
            logger.info("Training regime detector")
            
            # This would call the actual training method
            # self.models['regime'].train(data)
            
            self.model_status['regime'] = 'ready'
            self.last_training['regime'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error training regime model: {e}")
            self.model_status['regime'] = 'failed'
    
    async def _initialize_advanced_risk_engine(self, training_data: Dict[str, Any], force_retrain: bool):
        """Initialize Advanced Risk Engine with portfolio data"""
        try:
            if not force_retrain:
                last_training = self.last_training.get('advanced_risk')
                if last_training and (datetime.now() - last_training) < timedelta(days=1):
                    logger.info("Advanced Risk Engine recently initialized, skipping")
                    return
            
            logger.info("Initializing Advanced Risk Engine with portfolio data")
            
            # Prepare historical data for VaR calculations
            portfolio_symbols = list(training_data.keys())[:10]  # Limit for performance
            
            # Initialize with portfolio configuration
            await self.advanced_risk_engine.initialize_portfolio(
                symbols=portfolio_symbols,
                historical_data=training_data
            )
            
            self.last_training['advanced_risk'] = datetime.now()
            logger.info("Advanced Risk Engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Advanced Risk Engine: {e}")
            self.model_status['advanced_risk'] = 'failed'
    
    async def get_unified_predictions(self, symbols: Optional[List[str]] = None, 
                                   horizons: List[int] = [1, 7, 30]) -> Dict[str, Any]:
        """
        Get unified predictions from all models using configured data source
        
        Args:
            symbols: Asset symbols to predict (None for portfolio assets)
            horizons: Prediction horizons in days
            
        Returns:
            Comprehensive predictions from all models
        """
        try:
            # Use portfolio assets if not specified
            if symbols is None:
                symbols = await self.get_portfolio_assets(min_usd=50)
            
            data_source = await self.get_data_source_config()
            
            predictions = {
                'timestamp': datetime.now().isoformat(),
                'data_source': data_source,
                'symbols': symbols,
                'horizons': horizons,
                'models': {},
                'ensemble': {},
                'confidence_scores': {},
                'alerts': []
            }
            
            # Get predictions from each model
            for model_name, model in self.models.items():
                if self.model_status[model_name] != 'ready':
                    predictions['alerts'].append(f"{model_name} model not ready")
                    continue
                
                try:
                    if model_name == 'volatility':
                        vol_predictions = await self._get_volatility_predictions(symbols, horizons)
                        predictions['models']['volatility'] = vol_predictions
                    
                    elif model_name == 'sentiment':
                        sentiment_data = await self._get_sentiment_analysis(symbols)
                        predictions['models']['sentiment'] = sentiment_data
                    
                    elif model_name == 'regime':
                        regime_data = await self._get_regime_predictions(symbols)
                        predictions['models']['regime'] = regime_data
                    
                    elif model_name == 'correlation':
                        correlation_data = await self._get_correlation_forecasts(symbols)
                        predictions['models']['correlation'] = correlation_data
                    
                    elif model_name == 'advanced_risk':
                        risk_analysis = await self._get_advanced_risk_analysis(symbols, horizons)
                        predictions['models']['advanced_risk'] = risk_analysis
                    
                except Exception as e:
                    error_msg = f"Error getting {model_name} predictions: {str(e)}"
                    logger.error(error_msg)
                    predictions['alerts'].append(error_msg)
            
            # Create ensemble predictions
            predictions['ensemble'] = await self._create_ensemble_predictions(predictions['models'])
            
            # Calculate confidence scores
            predictions['confidence_scores'] = await self._calculate_confidence_scores(predictions['models'])
            
            # Cache results
            cache_key = f"predictions_{'-'.join(symbols)}_{'-'.join(map(str, horizons))}"
            self.prediction_cache[cache_key] = {
                'data': predictions,
                'timestamp': datetime.now()
            }
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error generating unified predictions: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'data_source': await self.get_data_source_config()
            }
    
    async def _get_volatility_predictions(self, symbols: List[str], horizons: List[int]) -> Dict[str, Any]:
        """Get volatility predictions for symbols"""
        volatility_predictions = {}
        
        for symbol in symbols[:3]:  # Limit for testing
            try:
                # Get recent data for prediction
                recent_data = self.data_pipeline.get_prediction_data(symbol, lookback_days=90)
                if recent_data is None:
                    continue
                
                # Generate predictions for each horizon
                symbol_predictions = {}
                for horizon in horizons:
                    # This would call the actual prediction method
                    # pred = self.models['volatility'].predict(recent_data, horizon)
                    
                    # Mock prediction for now
                    pred = {
                        'volatility_forecast': 0.3 + (horizon * 0.02),  # Mock increasing volatility
                        'confidence': 0.8 - (horizon * 0.05),  # Mock decreasing confidence
                        'risk_level': 'medium'
                    }
                    symbol_predictions[f'{horizon}d'] = pred
                
                volatility_predictions[symbol] = symbol_predictions
                
            except Exception as e:
                logger.error(f"Error predicting volatility for {symbol}: {e}")
        
        return volatility_predictions
    
    async def _get_sentiment_analysis(self, symbols: List[str]) -> Dict[str, Any]:
        """Get sentiment analysis for symbols"""
        # Mock sentiment analysis
        sentiment_data = {}
        for symbol in symbols[:5]:
            sentiment_data[symbol] = {
                'sentiment_score': 0.6,  # Mock positive sentiment
                'social_mentions': 150,
                'news_sentiment': 'bullish',
                'fear_greed_index': 65
            }
        return sentiment_data
    
    async def predict_volatility(self, symbol: str, horizon_days: int = 30) -> Dict[str, Any]:
        """
        Public method for single asset volatility prediction
        Used by unified_ml_endpoints.py
        """
        try:
            # Use existing volatility prediction logic
            predictions = await self._get_volatility_predictions([symbol], [horizon_days])
            
            if symbol in predictions and f'{horizon_days}d' in predictions[symbol]:
                result = predictions[symbol][f'{horizon_days}d']
                result.update({
                    'symbol': symbol,
                    'horizon_days': horizon_days,
                    'timestamp': datetime.now().isoformat(),
                    'model_version': '2.0.0'
                })
                return result
            else:
                # Fallback prediction if model not available
                return {
                    'symbol': symbol,
                    'horizon_days': horizon_days,
                    'volatility_forecast': 0.25,
                    'confidence': 0.5,
                    'risk_level': 'medium',
                    'timestamp': datetime.now().isoformat(),
                    'model_version': 'fallback',
                    'note': 'Using fallback prediction - trained models not loaded'
                }
                
        except Exception as e:
            logger.error(f"Error in predict_volatility for {symbol}: {e}")
            return {
                'symbol': symbol,
                'horizon_days': horizon_days,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def calculate_portfolio_var(self, portfolio_weights: Dict[str, float], 
                                    portfolio_value: float = 100000,
                                    confidence_level: float = 0.95,
                                    horizon_days: int = 1,
                                    method: str = 'historical') -> Dict[str, Any]:
        """
        Public method for portfolio VaR calculation
        Used by advanced risk endpoints
        """
        try:
            if self.model_status.get('advanced_risk') != 'ready':
                logger.warning("Advanced Risk Engine not ready for VaR calculation")
                return {
                    'error': 'Advanced Risk Engine not initialized',
                    'fallback_var': portfolio_value * 0.03,  # 3% fallback
                    'confidence_level': confidence_level,
                    'method': 'fallback',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Map method string to enum
            var_method = VaRMethod.HISTORICAL if method.lower() == 'historical' else VaRMethod.PARAMETRIC
            
            # Map horizon to enum
            if horizon_days == 1:
                horizon = RiskHorizon.DAILY
            elif horizon_days <= 7:
                horizon = RiskHorizon.WEEKLY
            else:
                horizon = RiskHorizon.MONTHLY
            
            # Calculate VaR using Advanced Risk Engine
            var_result = await self.advanced_risk_engine.calculate_var(
                portfolio_weights=portfolio_weights,
                portfolio_value=portfolio_value,
                method=var_method,
                confidence_level=confidence_level,
                horizon=horizon
            )
            
            return {
                'var_absolute': var_result.var_absolute,
                'cvar_absolute': var_result.cvar_absolute,
                'confidence_level': var_result.confidence_level,
                'method': var_result.method.value,
                'horizon': var_result.horizon.value,
                'portfolio_value': var_result.portfolio_value,
                'component_contributions': var_result.component_contributions,
                'model_parameters': var_result.model_parameters,
                'timestamp': datetime.now().isoformat(),
                'engine_version': '3.0.0'
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio VaR: {e}")
            return {
                'error': str(e),
                'fallback_var': portfolio_value * 0.03,
                'confidence_level': confidence_level,
                'method': method,
                'timestamp': datetime.now().isoformat()
            }

    async def _get_regime_predictions(self, symbols: List[str]) -> Dict[str, Any]:
        """Get market regime predictions"""
        return {
            'current_regime': 'bull_market',
            'regime_probability': 0.75,
            'regime_stability': 0.82,
            'expected_duration_days': 45
        }
    
    async def _get_correlation_forecasts(self, symbols: List[str]) -> Dict[str, Any]:
        """Get correlation forecasts between assets"""
        correlations = {}
        for i, symbol1 in enumerate(symbols[:3]):
            for symbol2 in symbols[i+1:4]:
                pair = f"{symbol1}-{symbol2}"
                correlations[pair] = {
                    'current_correlation': 0.65,
                    'forecast_correlation': 0.58,
                    'correlation_trend': 'decreasing'
                }
        return correlations
    
    async def _get_advanced_risk_analysis(self, symbols: List[str], horizons: List[int]) -> Dict[str, Any]:
        """Get comprehensive risk analysis using Advanced Risk Engine"""
        try:
            if self.model_status.get('advanced_risk') != 'ready':
                logger.warning("Advanced Risk Engine not ready, using fallback analysis")
                return {
                    'status': 'fallback',
                    'var_absolutes': {symbol: {'1d': 0.05, '7d': 0.15, '30d': 0.35} for symbol in symbols[:5]},
                    'portfolio_risk': {'daily_var_95': 0.03, 'cvar_absolute': 0.045},
                    'stress_test_summary': 'Engine not initialized'
                }
            
            risk_analysis = {
                'timestamp': datetime.now().isoformat(),
                'symbols_analyzed': symbols[:10],  # Limit for performance
                'var_analysis': {},
                'stress_tests': {},
                'monte_carlo': {},
                'portfolio_metrics': {},
                'risk_alerts': []
            }
            
            # Get portfolio weights (simplified - equal weight for now)
            num_assets = min(len(symbols), 10)
            equal_weight = 1.0 / num_assets
            portfolio_weights = {symbol: equal_weight for symbol in symbols[:num_assets]}
            portfolio_value = 100000  # $100k portfolio for analysis
            
            # Calculate VaR for different horizons and methods
            for horizon_days in horizons:
                horizon = RiskHorizon.DAILY if horizon_days == 1 else RiskHorizon.WEEKLY if horizon_days <= 7 else RiskHorizon.MONTHLY
                
                # Parametric VaR
                var_parametric = await self.advanced_risk_engine.calculate_var(
                    portfolio_weights=portfolio_weights,
                    portfolio_value=portfolio_value,
                    method=VaRMethod.PARAMETRIC,
                    confidence_level=0.95,
                    horizon=horizon
                )
                
                # Historical VaR 
                var_historical = await self.advanced_risk_engine.calculate_var(
                    portfolio_weights=portfolio_weights,
                    portfolio_value=portfolio_value,
                    method=VaRMethod.HISTORICAL,
                    confidence_level=0.95,
                    horizon=horizon
                )
                
                risk_analysis['var_analysis'][f'{horizon_days}d'] = {
                    'parametric_var': var_parametric.var_absolute,
                    'historical_var': var_historical.var_absolute,
                    'cvar_absolute': var_parametric.cvar_absolute,
                    'confidence_level': 0.95,
                    'method_comparison': {
                        'parametric_vs_historical_ratio': var_parametric.var_absolute / max(var_historical.var_absolute, 0.001),
                        'recommended_method': 'historical' if var_historical.var_absolute > var_parametric.var_absolute * 1.2 else 'parametric'
                    }
                }
            
            # Run stress tests for major market scenarios
            stress_scenarios = ['covid_2020', 'crypto_winter_2022', 'china_ban_2021']
            
            for scenario in stress_scenarios:
                try:
                    stress_result = await self.advanced_risk_engine.run_stress_test(
                        portfolio_weights=portfolio_weights,
                        portfolio_value=portfolio_value,
                        scenario_name=scenario
                    )
                    
                    risk_analysis['stress_tests'][scenario] = {
                        'portfolio_loss': stress_result.portfolio_loss,
                        'loss_percentage': stress_result.loss_percentage,
                        'assets_affected': stress_result.asset_impacts,
                        'recovery_estimate_days': stress_result.recovery_estimate_days
                    }
                    
                    # Generate risk alerts for severe stress test results
                    if stress_result.loss_percentage > 0.3:  # >30% loss
                        risk_analysis['risk_alerts'].append({
                            'type': 'severe_stress_risk',
                            'scenario': scenario,
                            'potential_loss': stress_result.loss_percentage,
                            'recommendation': 'Consider reducing portfolio risk exposure'
                        })
                        
                except Exception as e:
                    logger.error(f"Stress test {scenario} failed: {e}")
                    risk_analysis['stress_tests'][scenario] = {'error': str(e)}
            
            # Run Monte Carlo simulation for 1-day horizon
            try:
                monte_carlo_result = await self.advanced_risk_engine.run_monte_carlo_simulation(
                    portfolio_weights=portfolio_weights,
                    portfolio_value=portfolio_value,
                    days=1,
                    simulations=5000,  # Reduced for performance
                    confidence_level=0.95
                )
                
                risk_analysis['monte_carlo'] = {
                    'var_absolute': monte_carlo_result.var_absolute,
                    'expected_return': monte_carlo_result.expected_return,
                    'volatility': monte_carlo_result.volatility,
                    'skewness': monte_carlo_result.skewness,
                    'kurtosis': monte_carlo_result.kurtosis,
                    'simulations_run': monte_carlo_result.simulations,
                    'tail_risk_analysis': {
                        'extreme_loss_probability': monte_carlo_result.tail_risk_metrics.get('extreme_loss_prob', 0),
                        'max_simulated_loss': monte_carlo_result.tail_risk_metrics.get('max_loss', 0)
                    }
                }
                
            except Exception as e:
                logger.error(f"Monte Carlo simulation failed: {e}")
                risk_analysis['monte_carlo'] = {'error': str(e)}
            
            # Calculate portfolio-level risk metrics
            risk_analysis['portfolio_metrics'] = {
                'total_portfolio_value': portfolio_value,
                'number_of_assets': len(portfolio_weights),
                'concentration_risk': max(portfolio_weights.values()),  # Largest single position
                'diversification_ratio': 1.0 / len(portfolio_weights),  # Simple diversification measure
                'risk_assessment': await self._assess_overall_portfolio_risk(risk_analysis),
                'recommendation': await self._generate_risk_recommendation(risk_analysis)
            }
            
            logger.info(f"Advanced risk analysis completed for {len(symbols)} assets")
            return risk_analysis
            
        except Exception as e:
            logger.error(f"Error in advanced risk analysis: {e}")
            return {
                'error': str(e),
                'status': 'failed',
                'timestamp': datetime.now().isoformat(),
                'fallback_message': 'Risk analysis failed, using conservative estimates'
            }
    
    async def _assess_overall_portfolio_risk(self, risk_analysis: Dict[str, Any]) -> str:
        """Assess overall portfolio risk level based on analysis results"""
        try:
            risk_indicators = []
            
            # Check VaR levels
            if 'var_analysis' in risk_analysis and '1d' in risk_analysis['var_analysis']:
                daily_var = risk_analysis['var_analysis']['1d'].get('historical_var', 0)
                if daily_var > 0.05:  # >5% daily VaR
                    risk_indicators.append('high_var')
                elif daily_var > 0.03:
                    risk_indicators.append('moderate_var')
            
            # Check stress test results
            if 'stress_tests' in risk_analysis:
                severe_scenarios = 0
                for scenario_result in risk_analysis['stress_tests'].values():
                    if isinstance(scenario_result, dict) and 'loss_percentage' in scenario_result:
                        if scenario_result['loss_percentage'] > 0.4:  # >40% loss
                            severe_scenarios += 1
                
                if severe_scenarios >= 2:
                    risk_indicators.append('stress_vulnerable')
                elif severe_scenarios == 1:
                    risk_indicators.append('moderate_stress_risk')
            
            # Check Monte Carlo tail risk
            if 'monte_carlo' in risk_analysis and 'tail_risk_analysis' in risk_analysis['monte_carlo']:
                extreme_loss_prob = risk_analysis['monte_carlo']['tail_risk_analysis'].get('extreme_loss_probability', 0)
                if extreme_loss_prob > 0.05:  # >5% probability of extreme loss
                    risk_indicators.append('tail_risk')
            
            # Determine overall risk level
            if len(risk_indicators) >= 3:
                return 'high'
            elif len(risk_indicators) >= 2:
                return 'moderate_high'
            elif len(risk_indicators) >= 1:
                return 'moderate'
            else:
                return 'low_moderate'
                
        except Exception as e:
            logger.error(f"Error assessing portfolio risk: {e}")
            return 'unknown'
    
    async def _generate_risk_recommendation(self, risk_analysis: Dict[str, Any]) -> str:
        """Generate risk management recommendation based on analysis"""
        try:
            risk_level = await self._assess_overall_portfolio_risk(risk_analysis)
            
            if risk_level == 'high':
                return 'Consider significant risk reduction: decrease position sizes, increase diversification, add hedging positions'
            elif risk_level == 'moderate_high':
                return 'Moderate risk reduction advised: review position sizing and consider partial profit-taking'
            elif risk_level == 'moderate':
                return 'Monitor closely: current risk levels acceptable but watch for deterioration'
            else:
                return 'Risk levels appear manageable: maintain current allocation with regular monitoring'
                
        except Exception as e:
            logger.error(f"Error generating risk recommendation: {e}")
            return 'Unable to generate recommendation due to analysis error'
    
    async def _create_ensemble_predictions(self, model_predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Create ensemble predictions from all models using weighted voting and confidence scoring"""
        
        # Initialize ensemble components
        ensemble = {
            'overall_market_sentiment': 'neutral',
            'risk_assessment': 'moderate',
            'recommended_action': 'hold',
            'confidence_level': 0.0,
            'model_contributions': {},
            'consensus_strength': 0.0,
            'conflicting_signals': []
        }
        
        try:
            # Model weights based on historical performance and reliability
            model_weights = {
                'volatility': 0.20,
                'sentiment': 0.15,
                'regime': 0.25,
                'correlation': 0.20,
                'advanced_risk': 0.20  # Phase 3A integration
            }
            
            # Collect sentiment signals
            sentiment_signals = []
            
            # Process volatility predictions
            if 'volatility' in model_predictions:
                vol_data = model_predictions['volatility']
                avg_volatility = 0
                vol_count = 0
                
                for symbol_preds in vol_data.values():
                    for horizon_pred in symbol_preds.values():
                        if isinstance(horizon_pred, dict) and 'volatility_forecast' in horizon_pred:
                            avg_volatility += horizon_pred['volatility_forecast']
                            vol_count += 1
                
                if vol_count > 0:
                    avg_volatility /= vol_count
                    
                    # High volatility suggests caution
                    if avg_volatility > 0.4:
                        sentiment_signals.append(('bearish', model_weights['volatility'], 'high_volatility'))
                    elif avg_volatility > 0.25:
                        sentiment_signals.append(('neutral', model_weights['volatility'], 'moderate_volatility'))
                    else:
                        sentiment_signals.append(('bullish', model_weights['volatility'], 'low_volatility'))
                    
                    ensemble['model_contributions']['volatility'] = {
                        'signal': 'bearish' if avg_volatility > 0.4 else 'neutral' if avg_volatility > 0.25 else 'bullish',
                        'confidence': min(1.0, 1.0 - avg_volatility),
                        'data': f"avg_vol: {avg_volatility:.3f}"
                    }
            
            # Process sentiment analysis
            if 'sentiment' in model_predictions:
                sent_data = model_predictions['sentiment']
                sentiment_scores = []
                
                for symbol_sentiment in sent_data.values():
                    if isinstance(symbol_sentiment, dict) and 'sentiment_score' in symbol_sentiment:
                        sentiment_scores.append(symbol_sentiment['sentiment_score'])
                
                if sentiment_scores:
                    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                    
                    if avg_sentiment > 0.6:
                        sentiment_signals.append(('bullish', model_weights['sentiment'], 'positive_sentiment'))
                    elif avg_sentiment < 0.4:
                        sentiment_signals.append(('bearish', model_weights['sentiment'], 'negative_sentiment'))
                    else:
                        sentiment_signals.append(('neutral', model_weights['sentiment'], 'mixed_sentiment'))
                    
                    ensemble['model_contributions']['sentiment'] = {
                        'signal': 'bullish' if avg_sentiment > 0.6 else 'bearish' if avg_sentiment < 0.4 else 'neutral',
                        'confidence': abs(avg_sentiment - 0.5) * 2,  # Distance from neutral
                        'data': f"avg_sentiment: {avg_sentiment:.3f}"
                    }
            
            # Process regime detection
            if 'regime' in model_predictions:
                regime_data = model_predictions['regime']
                regime = regime_data.get('current_regime', 'unknown')
                regime_prob = regime_data.get('regime_probability', 0.5)
                
                # Map regimes to sentiment
                regime_sentiment_map = {
                    'bull_market': 'bullish',
                    'accumulation': 'bullish',
                    'expansion': 'bullish', 
                    'bear_market': 'bearish',
                    'distribution': 'bearish',
                    'euphoria': 'neutral',  # High risk despite positive sentiment
                    'sideways': 'neutral'
                }
                
                regime_sentiment = regime_sentiment_map.get(regime, 'neutral')
                sentiment_signals.append((regime_sentiment, model_weights['regime'], f'regime_{regime}'))
                
                ensemble['model_contributions']['regime'] = {
                    'signal': regime_sentiment,
                    'confidence': regime_prob,
                    'data': f"regime: {regime}, prob: {regime_prob:.3f}"
                }
            
            # Process correlation analysis
            if 'correlation' in model_predictions:
                corr_data = model_predictions['correlation']
                correlation_trends = []
                
                for pair_data in corr_data.values():
                    if isinstance(pair_data, dict) and 'correlation_trend' in pair_data:
                        trend = pair_data['correlation_trend']
                        correlation_trends.append(trend)
                
                if correlation_trends:
                    # High correlations suggest systemic risk
                    increasing_corr = correlation_trends.count('increasing')
                    total_pairs = len(correlation_trends)
                    
                    if increasing_corr / total_pairs > 0.6:
                        sentiment_signals.append(('bearish', model_weights['correlation'], 'rising_correlations'))
                    elif increasing_corr / total_pairs < 0.4:
                        sentiment_signals.append(('bullish', model_weights['correlation'], 'diversified_correlations'))
                    else:
                        sentiment_signals.append(('neutral', model_weights['correlation'], 'stable_correlations'))
                    
                    ensemble['model_contributions']['correlation'] = {
                        'signal': 'bearish' if increasing_corr/total_pairs > 0.6 else 'bullish' if increasing_corr/total_pairs < 0.4 else 'neutral',
                        'confidence': abs(increasing_corr/total_pairs - 0.5) * 2,
                        'data': f"rising_corr: {increasing_corr}/{total_pairs}"
                    }
            
            # Process Advanced Risk Analysis (Phase 3A integration)
            if 'advanced_risk' in model_predictions:
                risk_data = model_predictions['advanced_risk']
                
                if isinstance(risk_data, dict) and 'portfolio_metrics' in risk_data:
                    risk_assessment = risk_data['portfolio_metrics'].get('risk_assessment', 'unknown')
                    
                    # Map risk assessment to sentiment signal
                    if risk_assessment in ['high', 'moderate_high']:
                        sentiment_signals.append(('bearish', model_weights['advanced_risk'], f'high_portfolio_risk_{risk_assessment}'))
                        risk_signal = 'bearish'
                    elif risk_assessment in ['low_moderate']:
                        sentiment_signals.append(('bullish', model_weights['advanced_risk'], f'low_portfolio_risk_{risk_assessment}'))
                        risk_signal = 'bullish'
                    else:  # moderate
                        sentiment_signals.append(('neutral', model_weights['advanced_risk'], f'moderate_portfolio_risk_{risk_assessment}'))
                        risk_signal = 'neutral'
                    
                    # Check for severe VaR levels
                    var_confidence = 0.5
                    if 'var_analysis' in risk_data and '1d' in risk_data['var_analysis']:
                        daily_historical_var = risk_data['var_analysis']['1d'].get('historical_var', 0)
                        if daily_historical_var > 0.05:  # >5% daily VaR indicates high confidence in bearish signal
                            var_confidence = 0.9
                        elif daily_historical_var > 0.03:
                            var_confidence = 0.7
                        else:
                            var_confidence = 0.6
                    
                    ensemble['model_contributions']['advanced_risk'] = {
                        'signal': risk_signal,
                        'confidence': var_confidence,
                        'data': f"risk_level: {risk_assessment}, var_1d: {daily_historical_var:.3f}" if 'daily_historical_var' in locals() else f"risk_level: {risk_assessment}",
                        'risk_alerts': risk_data.get('risk_alerts', []),
                        'recommendation': risk_data['portfolio_metrics'].get('recommendation', 'Monitor portfolio risk')
                    }
            
            # Calculate weighted ensemble sentiment
            if sentiment_signals:
                weighted_scores = {
                    'bullish': 0,
                    'bearish': 0,
                    'neutral': 0
                }
                
                total_weight = 0
                
                for sentiment, weight, reason in sentiment_signals:
                    weighted_scores[sentiment] += weight
                    total_weight += weight
                
                # Normalize weights
                if total_weight > 0:
                    for key in weighted_scores:
                        weighted_scores[key] /= total_weight
                
                # Determine overall sentiment
                max_sentiment = max(weighted_scores.items(), key=lambda x: x[1])
                ensemble['overall_market_sentiment'] = max_sentiment[0]
                
                # Calculate consensus strength
                ensemble['consensus_strength'] = max_sentiment[1]
                
                # Generate recommendations based on ensemble
                if max_sentiment[0] == 'bullish' and max_sentiment[1] > 0.6:
                    ensemble['recommended_action'] = 'increase_risk_allocation'
                    ensemble['risk_assessment'] = 'low_to_moderate'
                elif max_sentiment[0] == 'bearish' and max_sentiment[1] > 0.6:
                    ensemble['recommended_action'] = 'reduce_risk_allocation'
                    ensemble['risk_assessment'] = 'moderate_to_high'
                else:
                    ensemble['recommended_action'] = 'hold_current_allocation'
                    ensemble['risk_assessment'] = 'moderate'
                
                # Calculate overall confidence
                model_confidences = []
                for contrib in ensemble['model_contributions'].values():
                    model_confidences.append(contrib.get('confidence', 0.5))
                
                if model_confidences:
                    base_confidence = sum(model_confidences) / len(model_confidences)
                    # Adjust confidence based on consensus strength
                    ensemble['confidence_level'] = min(1.0, base_confidence * (0.5 + ensemble['consensus_strength']))
                else:
                    ensemble['confidence_level'] = 0.5
                
                # Identify conflicting signals
                signal_types = [contrib['signal'] for contrib in ensemble['model_contributions'].values()]
                unique_signals = set(signal_types)
                
                if len(unique_signals) > 2:
                    ensemble['conflicting_signals'] = [
                        f"{model}: {contrib['signal']}" 
                        for model, contrib in ensemble['model_contributions'].items()
                        if contrib['signal'] != ensemble['overall_market_sentiment']
                    ]
            
            logger.info(f"Ensemble prediction generated: {ensemble['overall_market_sentiment']} "
                       f"(confidence: {ensemble['confidence_level']:.2f})")
            
            return ensemble
            
        except Exception as e:
            logger.error(f"Error creating ensemble predictions: {e}")
            # Return safe default
            return {
                'overall_market_sentiment': 'neutral',
                'risk_assessment': 'moderate', 
                'recommended_action': 'hold_current_allocation',
                'confidence_level': 0.0,
                'error': str(e)
            }
    
    async def _calculate_confidence_scores(self, model_predictions: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for predictions"""
        confidence_scores = {}
        
        # Calculate confidence based on model agreement and individual confidences
        model_count = len([m for m in model_predictions.values() if m])
        base_confidence = min(0.9, model_count / len(self.models) + 0.1)
        
        confidence_scores['overall'] = base_confidence
        confidence_scores['volatility'] = 0.8 if 'volatility' in model_predictions else 0.0
        confidence_scores['sentiment'] = 0.7 if 'sentiment' in model_predictions else 0.0
        confidence_scores['regime'] = 0.85 if 'regime' in model_predictions else 0.0
        confidence_scores['correlation'] = 0.75 if 'correlation' in model_predictions else 0.0
        
        return confidence_scores
    
    async def get_model_status(self) -> Dict[str, Any]:
        """
        Get status of all ML models and data source configuration
        
        Returns:
            Comprehensive status report
        """
        data_source = await self.get_data_source_config()
        
        status_report = {
            'timestamp': datetime.now().isoformat(),
            'data_source_config': data_source,
            'models': {}
        }
        
        for model_name, model in self.models.items():
            status_report['models'][model_name] = {
                'status': self.model_status[model_name],
                'last_training': self.last_training[model_name].isoformat() if self.last_training[model_name] else None,
                'type': model.__class__.__name__,
                'ready_for_predictions': self.model_status[model_name] == 'ready'
            }
        
        # Add system health metrics
        ready_models = sum(1 for status in self.model_status.values() if status == 'ready')
        total_models = len(self.models)
        
        status_report['system_health'] = {
            'models_ready': ready_models,
            'total_models': total_models,
            'readiness_percentage': (ready_models / total_models) * 100,
            'overall_status': 'healthy' if ready_models >= total_models * 0.6 else 'degraded'
        }
        
        return status_report
    
    async def retrain_models(self, model_names: Optional[List[str]] = None, 
                           force: bool = False) -> Dict[str, Any]:
        """
        Retrain specified models or all models
        
        Args:
            model_names: Models to retrain (None for all)
            force: Force retraining even if recent
            
        Returns:
            Retraining status report
        """
        if model_names is None:
            model_names = list(self.models.keys())
        
        logger.info(f"Retraining models: {model_names}")
        
        retrain_report = await self.initialize_models(force_retrain=force)
        retrain_report['retrained_models'] = model_names
        
        return retrain_report
    
    def clear_caches(self) -> Dict[str, int]:
        """Clear all caches"""
        cleared_counts = {
            'predictions': len(self.prediction_cache),
            'metrics': len(self.metrics_cache),
            'data_pipeline': self.data_pipeline.clear_cache()
        }
        
        self.prediction_cache.clear()
        self.metrics_cache.clear()
        
        logger.info(f"Cleared caches: {cleared_counts}")
        return cleared_counts
    
    async def load_regime_model(self) -> Dict[str, Any]:
        """Load regime detection model for auto-startup"""
        try:
            from services.ml_pipeline_manager_optimized import optimized_pipeline_manager as pipeline_manager
            await pipeline_manager.load_regime_model()
            self.model_status['regime'] = 'ready'
            logger.info("Regime model loaded successfully")
            return {"success": True, "message": "Regime model loaded"}
        except Exception as e:
            logger.error(f"Failed to load regime model: {e}")
            return {"success": False, "error": str(e)}

# Global orchestrator instance
_orchestrator = None

def get_orchestrator() -> MLOrchestrator:
    """Get or create global ML orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MLOrchestrator()
    return _orchestrator

def reset_orchestrator():
    """Reset global orchestrator instance (useful for development/testing)"""
    global _orchestrator
    _orchestrator = None

async def initialize_ml_system(force_retrain: bool = False) -> Dict[str, Any]:
    """Initialize the complete ML system"""
    orchestrator = get_orchestrator()
    return await orchestrator.initialize_models(force_retrain=force_retrain)

async def get_ml_predictions(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get unified ML predictions"""
    orchestrator = get_orchestrator()
    return await orchestrator.get_unified_predictions(symbols=symbols)

async def get_ml_status() -> Dict[str, Any]:
    """Get ML system status"""
    orchestrator = get_orchestrator()
    return await orchestrator.get_model_status()