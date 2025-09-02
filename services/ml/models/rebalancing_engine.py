"""
Automated Rebalancing Engine for Crypto Portfolios
ML-driven portfolio rebalancing with comprehensive safety mechanisms
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import json
import asyncio
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

# Import ML models for decision making
from .volatility_predictor import VolatilityPredictor
from .regime_detector import RegimeDetector
from .correlation_forecaster import CorrelationForecaster
from .sentiment_analyzer import SentimentAnalysisEngine
from ..data_pipeline import MLDataPipeline

logger = logging.getLogger(__name__)

class RebalanceReason(Enum):
    """Reasons for triggering rebalancing"""
    DRIFT_THRESHOLD = "drift_threshold"
    REGIME_CHANGE = "regime_change"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_SHIFT = "correlation_shift"
    SENTIMENT_EXTREME = "sentiment_extreme"
    SCHEDULED = "scheduled"
    EMERGENCY = "emergency"
    USER_REQUEST = "user_request"

class SafetyLevel(Enum):
    """Safety levels for rebalancing operations"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    EMERGENCY_ONLY = "emergency_only"

@dataclass
class RebalanceSignal:
    """Signal to trigger portfolio rebalancing"""
    reason: RebalanceReason
    severity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    recommended_action: str
    affected_assets: List[str]
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class AllocationTarget:
    """Target allocation for an asset"""
    symbol: str
    target_weight: float
    current_weight: float
    min_weight: float = 0.0
    max_weight: float = 1.0
    reasoning: str = ""
    confidence: float = 0.5

@dataclass
class RebalanceProposal:
    """Proposed rebalancing action"""
    proposal_id: str
    current_allocations: Dict[str, float]
    target_allocations: Dict[str, float] 
    trades_required: List[Dict[str, Any]]
    expected_cost: float
    expected_benefit: float
    risk_assessment: Dict[str, Any]
    safety_checks: Dict[str, bool]
    confidence: float
    reasoning: List[str]
    timestamp: datetime

class SafetyMechanisms:
    """Comprehensive safety mechanisms for automated rebalancing"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_safety_config()
        
    def _default_safety_config(self) -> Dict[str, Any]:
        """Default safety configuration"""
        return {
            # Trading limits
            "max_single_trade_pct": 0.15,  # Max 15% of portfolio in single trade
            "max_daily_trades_pct": 0.30,  # Max 30% portfolio turnover per day
            "min_trade_size_usd": 50,      # Min $50 trade size
            "max_trade_size_usd": 50000,   # Max $50k trade size
            
            # Risk limits
            "max_portfolio_concentration": 0.50,  # Max 50% in single asset
            "max_volatility_increase": 0.20,      # Max 20% volatility increase
            "min_diversification_ratio": 0.60,    # Minimum diversification
            "max_correlation_avg": 0.80,          # Max average correlation
            
            # Time constraints
            "min_rebalance_interval_hours": 6,    # Min 6 hours between rebalances
            "max_rebalance_frequency_daily": 3,   # Max 3 rebalances per day
            "cooling_period_hours": 24,           # 24h cooling period after large moves
            
            # Market conditions
            "max_market_volatility": 0.08,        # Pause if market vol > 8%
            "min_market_liquidity": 0.70,         # Min liquidity threshold
            "blackout_hours": [(22, 6)],          # UTC blackout hours (10pm-6am)
            
            # Emergency stops
            "max_portfolio_loss_1h": 0.05,        # 5% loss in 1 hour
            "max_portfolio_loss_24h": 0.15,       # 15% loss in 24 hours
            "min_emergency_cash_pct": 0.05,       # Always keep 5% cash
        }
    
    def check_trading_limits(self, 
                           proposal: RebalanceProposal,
                           portfolio_value: float,
                           recent_trades: List[Dict]) -> Dict[str, bool]:
        """Check trading limit safety constraints"""
        safety_checks = {}
        
        # Check single trade size limits
        max_trade_value = max(abs(trade.get("value_usd", 0)) for trade in proposal.trades_required)
        max_trade_pct = max_trade_value / portfolio_value if portfolio_value > 0 else 0
        
        safety_checks["single_trade_limit"] = max_trade_pct <= self.config["max_single_trade_pct"]
        
        # Check daily trade volume
        daily_trade_value = sum(abs(trade.get("value_usd", 0)) for trade in proposal.trades_required)
        daily_trade_pct = daily_trade_value / portfolio_value if portfolio_value > 0 else 0
        
        safety_checks["daily_volume_limit"] = daily_trade_pct <= self.config["max_daily_trades_pct"]
        
        # Check minimum/maximum trade sizes
        for trade in proposal.trades_required:
            trade_value = abs(trade.get("value_usd", 0))
            if trade_value > 0:  # Skip zero-value trades
                safety_checks[f"min_trade_size_{trade.get('symbol', 'unknown')}"] = \
                    trade_value >= self.config["min_trade_size_usd"]
                safety_checks[f"max_trade_size_{trade.get('symbol', 'unknown')}"] = \
                    trade_value <= self.config["max_trade_size_usd"]
        
        return safety_checks
    
    def check_risk_limits(self, 
                         target_allocations: Dict[str, float],
                         predicted_volatilities: Dict[str, float],
                         correlation_matrix: pd.DataFrame) -> Dict[str, bool]:
        """Check risk limit safety constraints"""
        safety_checks = {}
        
        # Check concentration limits
        max_allocation = max(target_allocations.values()) if target_allocations else 0
        safety_checks["concentration_limit"] = max_allocation <= self.config["max_portfolio_concentration"]
        
        # Check portfolio volatility increase
        if predicted_volatilities and len(target_allocations) > 1:
            # Calculate weighted portfolio volatility
            weights = np.array(list(target_allocations.values()))
            vols = np.array([predicted_volatilities.get(symbol, 0.1) 
                           for symbol in target_allocations.keys()])
            
            # Simple portfolio volatility (assuming no correlation data)
            if correlation_matrix is not None and len(correlation_matrix) >= len(target_allocations):
                # Use correlation matrix for accurate portfolio volatility
                portfolio_vol = np.sqrt(np.dot(weights, np.dot(correlation_matrix.values, weights)))
            else:
                # Fallback: weighted average volatility
                portfolio_vol = np.dot(weights, vols)
            
            safety_checks["volatility_increase"] = portfolio_vol <= self.config["max_volatility_increase"]
        else:
            safety_checks["volatility_increase"] = True
        
        # Check diversification ratio (if correlation data available)
        if correlation_matrix is not None and len(correlation_matrix) >= 2:
            avg_correlation = correlation_matrix.values[np.triu_indices_from(
                correlation_matrix.values, k=1)].mean()
            diversification_ratio = 1 - avg_correlation
            
            safety_checks["diversification_ratio"] = \
                diversification_ratio >= self.config["min_diversification_ratio"]
            safety_checks["correlation_limit"] = avg_correlation <= self.config["max_correlation_avg"]
        else:
            safety_checks["diversification_ratio"] = True
            safety_checks["correlation_limit"] = True
        
        return safety_checks
    
    def check_timing_constraints(self, 
                               last_rebalance: Optional[datetime],
                               recent_rebalances: List[datetime]) -> Dict[str, bool]:
        """Check timing constraint safety mechanisms"""
        safety_checks = {}
        current_time = datetime.now()
        
        # Check minimum interval between rebalances
        if last_rebalance:
            time_since_last = (current_time - last_rebalance).total_seconds() / 3600
            safety_checks["min_interval"] = time_since_last >= self.config["min_rebalance_interval_hours"]
        else:
            safety_checks["min_interval"] = True
        
        # Check daily rebalance frequency
        today_rebalances = [r for r in recent_rebalances 
                          if (current_time - r).days == 0]
        safety_checks["daily_frequency"] = len(today_rebalances) < self.config["max_rebalance_frequency_daily"]
        
        # Check blackout hours
        current_hour = current_time.hour
        in_blackout = any(start <= current_hour < end or (start > end and (current_hour >= start or current_hour < end))
                         for start, end in self.config["blackout_hours"])
        safety_checks["blackout_hours"] = not in_blackout
        
        return safety_checks
    
    def check_market_conditions(self, 
                              market_volatility: float,
                              market_liquidity: float,
                              portfolio_performance: Dict[str, float]) -> Dict[str, bool]:
        """Check market condition safety constraints"""
        safety_checks = {}
        
        # Check market volatility
        safety_checks["market_volatility"] = market_volatility <= self.config["max_market_volatility"]
        
        # Check market liquidity
        safety_checks["market_liquidity"] = market_liquidity >= self.config["min_market_liquidity"]
        
        # Check emergency stop conditions
        loss_1h = portfolio_performance.get("loss_1h", 0)
        loss_24h = portfolio_performance.get("loss_24h", 0)
        
        safety_checks["emergency_stop_1h"] = loss_1h <= self.config["max_portfolio_loss_1h"]
        safety_checks["emergency_stop_24h"] = loss_24h <= self.config["max_portfolio_loss_24h"]
        
        return safety_checks

class RebalancingEngine:
    """
    Main automated rebalancing engine with ML integration and safety mechanisms
    """
    
    def __init__(self, 
                 safety_level: SafetyLevel = SafetyLevel.MODERATE,
                 model_dir: str = "models/rebalancing"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.safety_level = safety_level
        self.safety_mechanisms = SafetyMechanisms()
        
        # Initialize ML models
        self.volatility_predictor = VolatilityPredictor()
        self.regime_detector = RegimeDetector()
        self.correlation_forecaster = CorrelationForecaster()
        self.sentiment_engine = SentimentAnalysisEngine()
        self.data_pipeline = MLDataPipeline()
        
        # Configuration
        self.config = self._load_config()
        
        # State tracking
        self.last_rebalance = None
        self.recent_rebalances = []
        self.active_signals = []
        
        logger.info(f"RebalancingEngine initialized with safety level: {safety_level.value}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load rebalancing configuration"""
        config_file = self.model_dir / "rebalancing_config.json"
        
        default_config = {
            # Rebalancing triggers
            "drift_threshold": 0.15,           # 15% drift from target
            "regime_change_threshold": 0.8,    # 80% confidence for regime change
            "volatility_spike_threshold": 2.0,  # 2x normal volatility
            "sentiment_extreme_threshold": 0.7, # 70% extreme sentiment
            
            # Target allocation parameters
            "min_allocation": 0.02,            # Min 2% per asset
            "max_allocation": 0.40,            # Max 40% per asset
            "cash_buffer": 0.05,               # 5% cash buffer
            
            # Risk parameters by safety level
            "risk_budgets": {
                SafetyLevel.CONSERVATIVE.value: {
                    "max_volatility": 0.15,
                    "max_drawdown": 0.10,
                    "rebalance_frequency": "weekly"
                },
                SafetyLevel.MODERATE.value: {
                    "max_volatility": 0.25,
                    "max_drawdown": 0.15,
                    "rebalance_frequency": "daily"
                },
                SafetyLevel.AGGRESSIVE.value: {
                    "max_volatility": 0.40,
                    "max_drawdown": 0.25,
                    "rebalance_frequency": "hourly"
                },
                SafetyLevel.EMERGENCY_ONLY.value: {
                    "max_volatility": 0.50,
                    "max_drawdown": 0.30,
                    "rebalance_frequency": "emergency"
                }
            }
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                default_config.update(loaded_config)
            except Exception as e:
                logger.warning(f"Error loading config: {e}. Using defaults.")
        
        return default_config
    
    async def analyze_rebalancing_signals(self, 
                                        portfolio: Dict[str, float],
                                        target_allocations: Optional[Dict[str, float]] = None) -> List[RebalanceSignal]:
        """
        Analyze market conditions and generate rebalancing signals
        
        Args:
            portfolio: Current portfolio allocations {symbol: weight}
            target_allocations: Strategic target allocations
            
        Returns:
            List of rebalancing signals
        """
        signals = []
        
        try:
            symbols = list(portfolio.keys())
            logger.info(f"Analyzing rebalancing signals for {len(symbols)} assets")
            
            # 1. Check allocation drift
            if target_allocations:
                drift_signals = self._check_allocation_drift(portfolio, target_allocations)
                signals.extend(drift_signals)
            
            # 2. Check regime changes
            regime_signals = await self._check_regime_changes(symbols)
            signals.extend(regime_signals)
            
            # 3. Check volatility spikes
            volatility_signals = await self._check_volatility_spikes(symbols)
            signals.extend(volatility_signals)
            
            # 4. Check correlation shifts
            correlation_signals = await self._check_correlation_shifts(symbols)
            signals.extend(correlation_signals)
            
            # 5. Check sentiment extremes
            sentiment_signals = await self._check_sentiment_extremes(symbols)
            signals.extend(sentiment_signals)
            
            # Filter and prioritize signals
            signals = self._prioritize_signals(signals)
            
            logger.info(f"Generated {len(signals)} rebalancing signals")
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing rebalancing signals: {e}")
            return []
    
    def _check_allocation_drift(self, 
                              current: Dict[str, float], 
                              target: Dict[str, float]) -> List[RebalanceSignal]:
        """Check for allocation drift from targets"""
        signals = []
        
        for symbol in target.keys():
            current_weight = current.get(symbol, 0.0)
            target_weight = target[symbol]
            
            drift = abs(current_weight - target_weight)
            drift_pct = drift / target_weight if target_weight > 0 else 0
            
            if drift_pct > self.config["drift_threshold"]:
                severity = min(1.0, drift_pct / 0.5)  # Normalize to [0, 1]
                
                signals.append(RebalanceSignal(
                    reason=RebalanceReason.DRIFT_THRESHOLD,
                    severity=severity,
                    confidence=0.9,  # High confidence in drift calculation
                    recommended_action=f"Rebalance {symbol}: {current_weight:.1%} → {target_weight:.1%}",
                    affected_assets=[symbol],
                    timestamp=datetime.now(),
                    metadata={
                        "current_weight": current_weight,
                        "target_weight": target_weight,
                        "drift_pct": drift_pct
                    }
                ))
        
        return signals
    
    async def _check_regime_changes(self, symbols: List[str]) -> List[RebalanceSignal]:
        """Check for market regime changes"""
        signals = []
        
        try:
            # Get recent multi-asset data for regime detection
            multi_asset_data = {}
            for symbol in symbols[:6]:  # Limit for performance
                recent_data = self.data_pipeline.get_prediction_data(symbol, 60)
                if recent_data is not None:
                    multi_asset_data[symbol] = recent_data
            
            if len(multi_asset_data) >= 3:
                # Load regime detector model
                if self.regime_detector.neural_model is None:
                    self.regime_detector.load_model()
                
                if self.regime_detector.neural_model is not None:
                    regime_prediction = self.regime_detector.predict_regime(
                        multi_asset_data, return_probabilities=True
                    )
                    
                    confidence = regime_prediction.get('confidence', 0.0)
                    if confidence > self.config["regime_change_threshold"]:
                        regime_name = regime_prediction.get('regime_name', 'Unknown')
                        
                        signals.append(RebalanceSignal(
                            reason=RebalanceReason.REGIME_CHANGE,
                            severity=confidence,
                            confidence=confidence,
                            recommended_action=f"Adapt to {regime_name} regime",
                            affected_assets=list(multi_asset_data.keys()),
                            timestamp=datetime.now(),
                            metadata=regime_prediction
                        ))
        
        except Exception as e:
            logger.warning(f"Error checking regime changes: {e}")
        
        return signals
    
    async def _check_volatility_spikes(self, symbols: List[str]) -> List[RebalanceSignal]:
        """Check for volatility spikes"""
        signals = []
        
        try:
            for symbol in symbols[:8]:  # Limit for performance
                # Get recent data for volatility analysis
                recent_data = self.data_pipeline.get_prediction_data(symbol, 30)
                
                if recent_data is not None and len(recent_data) >= 20:
                    # Calculate current vs historical volatility
                    returns = recent_data['close'].pct_change().dropna()
                    
                    current_vol = returns.tail(5).std() * np.sqrt(365)  # Recent 5-day volatility
                    historical_vol = returns.std() * np.sqrt(365)      # Full period volatility
                    
                    if historical_vol > 0:
                        vol_ratio = current_vol / historical_vol
                        
                        if vol_ratio > self.config["volatility_spike_threshold"]:
                            severity = min(1.0, (vol_ratio - 1.0) / 2.0)  # Normalize
                            
                            signals.append(RebalanceSignal(
                                reason=RebalanceReason.VOLATILITY_SPIKE,
                                severity=severity,
                                confidence=0.8,
                                recommended_action=f"Reduce {symbol} allocation due to volatility spike",
                                affected_assets=[symbol],
                                timestamp=datetime.now(),
                                metadata={
                                    "current_volatility": current_vol,
                                    "historical_volatility": historical_vol,
                                    "volatility_ratio": vol_ratio
                                }
                            ))
        
        except Exception as e:
            logger.warning(f"Error checking volatility spikes: {e}")
        
        return signals
    
    async def _check_correlation_shifts(self, symbols: List[str]) -> List[RebalanceSignal]:
        """Check for significant correlation shifts"""
        signals = []
        
        try:
            if len(symbols) >= 4:
                # Get recent data for correlation analysis
                multi_asset_data = {}
                for symbol in symbols[:6]:
                    recent_data = self.data_pipeline.get_prediction_data(symbol, 90)
                    if recent_data is not None:
                        multi_asset_data[symbol] = recent_data
                
                if len(multi_asset_data) >= 4:
                    # Load correlation forecaster
                    if not self.correlation_forecaster.models:
                        self.correlation_forecaster.load_models()
                    
                    if self.correlation_forecaster.models:
                        correlation_analysis = self.correlation_forecaster.analyze_correlation_changes(
                            multi_asset_data, lookback_days=60
                        )
                        
                        if 'market_correlation_level' in correlation_analysis:
                            market_level = correlation_analysis['market_correlation_level']
                            current_corr = market_level.get('current', 0.5)
                            
                            # Check for extreme correlation levels
                            if current_corr > 0.8 or current_corr < 0.2:
                                severity = abs(current_corr - 0.5) * 2  # Normalize around 0.5
                                
                                action = "Increase diversification" if current_corr > 0.8 else "Exploit diversification opportunity"
                                
                                signals.append(RebalanceSignal(
                                    reason=RebalanceReason.CORRELATION_SHIFT,
                                    severity=severity,
                                    confidence=0.7,
                                    recommended_action=action,
                                    affected_assets=list(multi_asset_data.keys()),
                                    timestamp=datetime.now(),
                                    metadata=correlation_analysis
                                ))
        
        except Exception as e:
            logger.warning(f"Error checking correlation shifts: {e}")
        
        return signals
    
    async def _check_sentiment_extremes(self, symbols: List[str]) -> List[RebalanceSignal]:
        """Check for extreme sentiment conditions"""
        signals = []
        
        try:
            # Analyze market sentiment
            sentiment_analysis = await self.sentiment_engine.analyze_market_sentiment(
                symbols[:5], days=3  # Quick sentiment check
            )
            
            market_overview = sentiment_analysis.get('market_overview', {})
            overall_sentiment = market_overview.get('overall_sentiment', 0.0)
            overall_confidence = market_overview.get('overall_confidence', 0.0)
            
            # Check for extreme sentiment
            if abs(overall_sentiment) > self.config["sentiment_extreme_threshold"] and overall_confidence > 0.6:
                severity = abs(overall_sentiment)
                
                if overall_sentiment > 0:
                    action = "Consider profit-taking due to extreme optimism"
                else:
                    action = "Consider accumulation opportunity due to extreme pessimism"
                
                signals.append(RebalanceSignal(
                    reason=RebalanceReason.SENTIMENT_EXTREME,
                    severity=severity,
                    confidence=overall_confidence,
                    recommended_action=action,
                    affected_assets=symbols,
                    timestamp=datetime.now(),
                    metadata=sentiment_analysis
                ))
        
        except Exception as e:
            logger.warning(f"Error checking sentiment extremes: {e}")
        
        return signals
    
    def _prioritize_signals(self, signals: List[RebalanceSignal]) -> List[RebalanceSignal]:
        """Prioritize and filter rebalancing signals"""
        if not signals:
            return []
        
        # Calculate priority score for each signal
        for signal in signals:
            priority = signal.severity * signal.confidence
            
            # Apply reason-based multipliers
            if signal.reason == RebalanceReason.EMERGENCY:
                priority *= 3.0
            elif signal.reason == RebalanceReason.DRIFT_THRESHOLD:
                priority *= 1.5
            elif signal.reason == RebalanceReason.REGIME_CHANGE:
                priority *= 1.3
            
            signal.metadata['priority_score'] = priority
        
        # Sort by priority and return top signals
        signals.sort(key=lambda s: s.metadata['priority_score'], reverse=True)
        
        # Filter by safety level
        max_signals = {
            SafetyLevel.CONSERVATIVE: 2,
            SafetyLevel.MODERATE: 3,
            SafetyLevel.AGGRESSIVE: 5,
            SafetyLevel.EMERGENCY_ONLY: 1
        }
        
        return signals[:max_signals[self.safety_level]]
    
    def generate_rebalance_proposal(self, 
                                  current_portfolio: Dict[str, float],
                                  signals: List[RebalanceSignal],
                                  portfolio_value: float,
                                  price_data: Dict[str, float]) -> Optional[RebalanceProposal]:
        """
        Generate a specific rebalancing proposal based on signals
        
        Args:
            current_portfolio: Current allocations {symbol: weight}
            signals: Rebalancing signals
            portfolio_value: Total portfolio value in USD
            price_data: Current prices {symbol: price_usd}
            
        Returns:
            RebalanceProposal or None if no action recommended
        """
        if not signals:
            return None
        
        try:
            logger.info(f"Generating rebalance proposal for {len(signals)} signals")
            
            # Calculate target allocations based on signals
            target_allocations = self._calculate_target_allocations(
                current_portfolio, signals, price_data
            )
            
            # Generate required trades
            trades_required = self._calculate_required_trades(
                current_portfolio, target_allocations, portfolio_value, price_data
            )
            
            # Estimate costs and benefits
            expected_cost = self._estimate_trading_costs(trades_required)
            expected_benefit = self._estimate_rebalance_benefit(signals)
            
            # Run safety checks
            safety_checks = self._run_comprehensive_safety_checks(
                current_portfolio, target_allocations, trades_required, 
                portfolio_value, price_data
            )
            
            # Assess overall risk
            risk_assessment = self._assess_rebalance_risk(
                current_portfolio, target_allocations, signals
            )
            
            # Calculate confidence
            confidence = self._calculate_proposal_confidence(signals, safety_checks)
            
            # Generate reasoning
            reasoning = self._generate_proposal_reasoning(signals, target_allocations)
            
            proposal = RebalanceProposal(
                proposal_id=f"rebal_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                current_allocations=current_portfolio.copy(),
                target_allocations=target_allocations,
                trades_required=trades_required,
                expected_cost=expected_cost,
                expected_benefit=expected_benefit,
                risk_assessment=risk_assessment,
                safety_checks=safety_checks,
                confidence=confidence,
                reasoning=reasoning,
                timestamp=datetime.now()
            )
            
            logger.info(f"Generated rebalance proposal: {len(trades_required)} trades, "
                       f"confidence: {confidence:.2f}")
            
            return proposal
            
        except Exception as e:
            logger.error(f"Error generating rebalance proposal: {e}")
            return None
    
    def _calculate_target_allocations(self, 
                                    current: Dict[str, float], 
                                    signals: List[RebalanceSignal],
                                    prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate optimal target allocations based on signals"""
        target = current.copy()
        
        # Apply signal-based adjustments
        for signal in signals:
            adjustment_factor = signal.severity * signal.confidence * 0.1  # Max 10% adjustment
            
            if signal.reason == RebalanceReason.DRIFT_THRESHOLD:
                # Restore toward target from metadata
                for asset in signal.affected_assets:
                    target_weight = signal.metadata.get('target_weight', current.get(asset, 0))
                    target[asset] = target_weight
            
            elif signal.reason == RebalanceReason.REGIME_CHANGE:
                # Adjust based on regime
                regime = signal.metadata.get('predicted_regime', 0)
                
                if regime == 0:  # Accumulation - increase allocation to quality assets
                    for asset in ['BTC', 'ETH']:
                        if asset in target:
                            target[asset] = min(target[asset] + adjustment_factor, 0.40)
                
                elif regime == 2:  # Euphoria - reduce risk
                    for asset in signal.affected_assets:
                        target[asset] = max(target[asset] - adjustment_factor, 0.02)
            
            elif signal.reason == RebalanceReason.VOLATILITY_SPIKE:
                # Reduce allocation to volatile assets
                for asset in signal.affected_assets:
                    target[asset] = max(target[asset] - adjustment_factor, 0.02)
            
            elif signal.reason == RebalanceReason.SENTIMENT_EXTREME:
                # Contrarian adjustment
                sentiment = signal.metadata.get('market_overview', {}).get('overall_sentiment', 0)
                
                if sentiment > 0.7:  # Extreme greed - reduce risk
                    for asset in signal.affected_assets:
                        target[asset] = max(target[asset] - adjustment_factor * 0.5, 0.02)
                elif sentiment < -0.7:  # Extreme fear - increase quality allocations
                    for asset in ['BTC', 'ETH']:
                        if asset in target:
                            target[asset] = min(target[asset] + adjustment_factor * 0.5, 0.40)
        
        # Normalize to sum to 1.0 (keeping cash buffer)
        total_allocation = sum(target.values())
        cash_buffer = self.config["cash_buffer"]
        
        if total_allocation > (1.0 - cash_buffer):
            normalization_factor = (1.0 - cash_buffer) / total_allocation
            for asset in target:
                target[asset] *= normalization_factor
        
        # Apply min/max constraints
        for asset in target:
            target[asset] = max(self.config["min_allocation"], 
                              min(target[asset], self.config["max_allocation"]))
        
        return target
    
    def _calculate_required_trades(self, 
                                 current: Dict[str, float],
                                 target: Dict[str, float], 
                                 portfolio_value: float,
                                 prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Calculate specific trades required for rebalancing"""
        trades = []
        
        all_assets = set(current.keys()) | set(target.keys())
        
        for asset in all_assets:
            current_weight = current.get(asset, 0.0)
            target_weight = target.get(asset, 0.0)
            
            weight_diff = target_weight - current_weight
            
            # Skip tiny changes
            if abs(weight_diff) < 0.005:  # Less than 0.5%
                continue
            
            value_diff = weight_diff * portfolio_value
            asset_price = prices.get(asset, 1.0)  # Default to $1 if price unknown
            
            if asset_price > 0:
                quantity_diff = value_diff / asset_price
                
                trade = {
                    "symbol": asset,
                    "action": "buy" if weight_diff > 0 else "sell",
                    "quantity": abs(quantity_diff),
                    "value_usd": abs(value_diff),
                    "current_weight": current_weight,
                    "target_weight": target_weight,
                    "weight_change": weight_diff,
                    "estimated_price": asset_price
                }
                
                trades.append(trade)
        
        return trades
    
    def _estimate_trading_costs(self, trades: List[Dict[str, Any]]) -> float:
        """Estimate total trading costs"""
        total_cost = 0.0
        
        for trade in trades:
            trade_value = trade.get("value_usd", 0)
            
            # Assume 0.1% trading fee + 0.05% slippage for crypto
            trading_fee = trade_value * 0.001
            slippage = trade_value * 0.0005
            
            total_cost += trading_fee + slippage
        
        return total_cost
    
    def _estimate_rebalance_benefit(self, signals: List[RebalanceSignal]) -> float:
        """Estimate expected benefit from rebalancing"""
        total_benefit = 0.0
        
        for signal in signals:
            # Benefit based on signal severity and confidence
            signal_benefit = signal.severity * signal.confidence * 1000  # $1000 max per signal
            
            # Adjust by signal type
            if signal.reason == RebalanceReason.DRIFT_THRESHOLD:
                signal_benefit *= 1.5  # Higher benefit for drift correction
            elif signal.reason == RebalanceReason.EMERGENCY:
                signal_benefit *= 2.0  # Highest benefit for emergency rebalancing
            
            total_benefit += signal_benefit
        
        return total_benefit
    
    def _run_comprehensive_safety_checks(self, 
                                       current: Dict[str, float],
                                       target: Dict[str, float],
                                       trades: List[Dict[str, Any]],
                                       portfolio_value: float,
                                       prices: Dict[str, float]) -> Dict[str, bool]:
        """Run all safety checks on the rebalancing proposal"""
        all_checks = {}
        
        # Create mock proposal for safety checks
        mock_proposal = RebalanceProposal(
            proposal_id="safety_check",
            current_allocations=current,
            target_allocations=target,
            trades_required=trades,
            expected_cost=0,
            expected_benefit=0,
            risk_assessment={},
            safety_checks={},
            confidence=0,
            reasoning=[],
            timestamp=datetime.now()
        )
        
        # Trading limits
        trading_checks = self.safety_mechanisms.check_trading_limits(
            mock_proposal, portfolio_value, []
        )
        all_checks.update(trading_checks)
        
        # Risk limits (simplified - no correlation matrix for now)
        predicted_vols = {asset: 0.25 for asset in target.keys()}  # Assume 25% volatility
        risk_checks = self.safety_mechanisms.check_risk_limits(
            target, predicted_vols, None
        )
        all_checks.update(risk_checks)
        
        # Timing constraints
        timing_checks = self.safety_mechanisms.check_timing_constraints(
            self.last_rebalance, self.recent_rebalances
        )
        all_checks.update(timing_checks)
        
        # Market conditions (simplified)
        market_checks = self.safety_mechanisms.check_market_conditions(
            0.05, 0.8, {"loss_1h": 0.0, "loss_24h": 0.0}
        )
        all_checks.update(market_checks)
        
        return all_checks
    
    def _assess_rebalance_risk(self, 
                             current: Dict[str, float],
                             target: Dict[str, float],
                             signals: List[RebalanceSignal]) -> Dict[str, Any]:
        """Assess the risk of the proposed rebalancing"""
        
        # Calculate allocation changes
        max_increase = max((target.get(asset, 0) - current.get(asset, 0)) 
                          for asset in set(current.keys()) | set(target.keys()))
        max_decrease = max((current.get(asset, 0) - target.get(asset, 0)) 
                          for asset in set(current.keys()) | set(target.keys()))
        
        # Risk factors
        concentration_risk = max(target.values()) if target else 0
        turnover = sum(abs(target.get(asset, 0) - current.get(asset, 0)) 
                      for asset in set(current.keys()) | set(target.keys())) / 2
        
        # Signal-based risk
        signal_risk = max(s.severity for s in signals) if signals else 0
        
        # Overall risk score
        risk_score = min(1.0, (concentration_risk + turnover + signal_risk) / 3)
        
        return {
            "overall_risk_score": risk_score,
            "concentration_risk": concentration_risk,
            "turnover_risk": turnover,
            "signal_risk": signal_risk,
            "max_allocation_increase": max_increase,
            "max_allocation_decrease": max_decrease,
            "risk_level": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low"
        }
    
    def _calculate_proposal_confidence(self, 
                                     signals: List[RebalanceSignal],
                                     safety_checks: Dict[str, bool]) -> float:
        """Calculate overall confidence in the rebalancing proposal"""
        
        # Signal confidence
        signal_confidence = np.mean([s.confidence * s.severity for s in signals]) if signals else 0
        
        # Safety check success rate
        safety_success_rate = sum(safety_checks.values()) / len(safety_checks) if safety_checks else 0
        
        # Combined confidence
        overall_confidence = (signal_confidence * 0.6 + safety_success_rate * 0.4)
        
        return min(1.0, max(0.0, overall_confidence))
    
    def _generate_proposal_reasoning(self, 
                                   signals: List[RebalanceSignal],
                                   target_allocations: Dict[str, float]) -> List[str]:
        """Generate human-readable reasoning for the proposal"""
        reasoning = []
        
        if signals:
            reasoning.append(f"Triggered by {len(signals)} market signals:")
            
            for signal in signals:
                reasoning.append(f"- {signal.recommended_action} (confidence: {signal.confidence:.1%})")
        
        # Allocation changes
        reasoning.append("Target allocation changes:")
        for asset, weight in sorted(target_allocations.items(), key=lambda x: x[1], reverse=True):
            reasoning.append(f"- {asset}: {weight:.1%}")
        
        return reasoning
    
    def evaluate_proposal(self, proposal: RebalanceProposal) -> Dict[str, Any]:
        """
        Evaluate a rebalancing proposal for approval
        
        Args:
            proposal: RebalanceProposal to evaluate
            
        Returns:
            Evaluation results with approval recommendation
        """
        evaluation = {
            "proposal_id": proposal.proposal_id,
            "timestamp": datetime.now().isoformat(),
            "approval_recommendation": "pending"
        }
        
        # Safety check evaluation
        safety_score = sum(proposal.safety_checks.values()) / len(proposal.safety_checks) if proposal.safety_checks else 0
        evaluation["safety_score"] = safety_score
        
        # Cost-benefit analysis
        net_benefit = proposal.expected_benefit - proposal.expected_cost
        evaluation["net_benefit"] = net_benefit
        evaluation["cost_benefit_ratio"] = proposal.expected_benefit / proposal.expected_cost if proposal.expected_cost > 0 else float('inf')
        
        # Risk evaluation
        risk_score = proposal.risk_assessment.get("overall_risk_score", 0.5)
        evaluation["risk_score"] = risk_score
        
        # Final recommendation
        if safety_score < 0.8:
            evaluation["approval_recommendation"] = "reject"
            evaluation["rejection_reason"] = "Failed safety checks"
        elif net_benefit < 0:
            evaluation["approval_recommendation"] = "reject"
            evaluation["rejection_reason"] = "Negative expected value"
        elif risk_score > 0.8 and self.safety_level != SafetyLevel.AGGRESSIVE:
            evaluation["approval_recommendation"] = "reject"
            evaluation["rejection_reason"] = "Risk too high for current safety level"
        elif proposal.confidence > 0.6:
            evaluation["approval_recommendation"] = "approve"
        else:
            evaluation["approval_recommendation"] = "review"
            evaluation["review_reason"] = "Low confidence - manual review recommended"
        
        return evaluation
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get current engine status and configuration"""
        return {
            "safety_level": self.safety_level.value,
            "last_rebalance": self.last_rebalance.isoformat() if self.last_rebalance else None,
            "recent_rebalances_count": len(self.recent_rebalances),
            "active_signals_count": len(self.active_signals),
            "ml_models_status": {
                "volatility_predictor": len(self.volatility_predictor.models),
                "regime_detector": self.regime_detector.neural_model is not None,
                "correlation_forecaster": len(self.correlation_forecaster.models),
                "sentiment_engine": len(self.sentiment_engine.collectors)
            },
            "configuration": self.config,
            "safety_mechanisms": self.safety_mechanisms.config
        }