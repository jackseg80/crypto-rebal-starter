"""
Advanced Backtesting Engine for Portfolio Strategies
Comprehensive backtesting with transaction costs, slippage, and realistic constraints
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class RebalanceFrequency(Enum):
    """Rebalancing frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly" 
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

class BacktestMetric(Enum):
    """Available backtest metrics"""
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    VOLATILITY = "volatility"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"
    WIN_RATE = "win_rate"
    TRANSACTION_COSTS = "transaction_costs"

@dataclass
class TransactionCosts:
    """Transaction cost model"""
    maker_fee: float = 0.001  # 0.1% maker fee
    taker_fee: float = 0.0015  # 0.15% taker fee
    slippage_bps: float = 5.0  # 5 basis points slippage
    min_trade_size: float = 10.0  # Minimum $10 trade
    
@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    transaction_costs: TransactionCosts = field(default_factory=TransactionCosts)
    benchmark: str = "BTC"  # Benchmark asset
    risk_free_rate: float = 0.02  # 2% annual
    max_position_size: float = 0.5  # Max 50% in single asset
    
@dataclass 
class BacktestResult:
    """Complete backtesting results"""
    config: BacktestConfig
    portfolio_value: pd.Series
    weights_history: pd.DataFrame
    trades_history: pd.DataFrame
    metrics: Dict[str, float]
    benchmark_performance: pd.Series
    monthly_returns: pd.Series
    annual_returns: pd.Series
    drawdowns: pd.Series
    risk_metrics: Dict[str, float]
    attribution: Dict[str, Dict]
    summary: Dict[str, any]

class PortfolioStrategy:
    """Base class for portfolio strategies"""
    
    def __init__(self, name: str):
        self.name = name
        
    def get_weights(self, date: pd.Timestamp, price_data: pd.DataFrame, 
                   current_weights: pd.Series, **kwargs) -> pd.Series:
        """
        Return target weights for given date
        Must be implemented by subclasses
        """
        raise NotImplementedError("Strategy must implement get_weights method")

class EqualWeightStrategy(PortfolioStrategy):
    """Equal weight strategy"""
    
    def __init__(self):
        super().__init__("Equal Weight")
    
    def get_weights(self, date: pd.Timestamp, price_data: pd.DataFrame,
                   current_weights: pd.Series, **kwargs) -> pd.Series:
        assets = price_data.columns
        return pd.Series(1.0 / len(assets), index=assets)

class MarketCapStrategy(PortfolioStrategy):
    """Market cap weighted strategy (proxy using price)"""
    
    def __init__(self):
        super().__init__("Market Cap Weighted")
    
    def get_weights(self, date: pd.Timestamp, price_data: pd.DataFrame,
                   current_weights: pd.Series, **kwargs) -> pd.Series:
        # Use prices as proxy for market cap
        prices = price_data.loc[date]
        weights = prices / prices.sum()
        return weights

class MomentumStrategy(PortfolioStrategy):
    """Momentum strategy based on past returns"""
    
    def __init__(self, lookback_days: int = 90):
        super().__init__(f"Momentum ({lookback_days}d)")
        self.lookback_days = lookback_days
    
    def get_weights(self, date: pd.Timestamp, price_data: pd.DataFrame,
                   current_weights: pd.Series, **kwargs) -> pd.Series:
        
        # Calculate momentum scores
        try:
            end_idx = price_data.index.get_indexer([date], method='nearest')[0]
        except (KeyError, IndexError):
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        start_idx = max(0, end_idx - self.lookback_days)
        
        if start_idx >= end_idx:
            # Fallback to equal weights
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        
        period_data = price_data.iloc[start_idx:end_idx+1]
        returns = (period_data.iloc[-1] / period_data.iloc[0] - 1)
        
        # Rank assets by momentum
        momentum_ranks = returns.rank(ascending=False)
        
        # Exponential weighting based on rank
        weights = np.exp(-momentum_ranks / len(returns))
        weights = weights / weights.sum()
        
        return weights

class MeanReversionStrategy(PortfolioStrategy):
    """Mean reversion strategy"""
    
    def __init__(self, lookback_days: int = 30):
        super().__init__(f"Mean Reversion ({lookback_days}d)")
        self.lookback_days = lookback_days
    
    def get_weights(self, date: pd.Timestamp, price_data: pd.DataFrame,
                   current_weights: pd.Series, **kwargs) -> pd.Series:
        
        # Calculate mean reversion scores
        try:
            end_idx = price_data.index.get_indexer([date], method='nearest')[0]
        except (KeyError, IndexError):
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        start_idx = max(0, end_idx - self.lookback_days)
        
        if start_idx >= end_idx:
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        
        period_data = price_data.iloc[start_idx:end_idx+1]
        recent_returns = period_data.pct_change().tail(7).mean()  # Last week average
        long_term_mean = period_data.pct_change().mean()
        
        # Deviation from long-term mean (negative deviation = underperformed = higher weight)
        deviations = long_term_mean - recent_returns
        
        # Convert to positive weights
        if deviations.min() < 0:
            deviations = deviations - deviations.min()
        
        weights = deviations / deviations.sum() if deviations.sum() > 0 else pd.Series(1.0 / len(deviations), index=deviations.index)
        
        return weights

class RiskParityStrategy(PortfolioStrategy):
    """Risk parity strategy (simplified)"""
    
    def __init__(self, vol_lookback: int = 30):
        super().__init__(f"Risk Parity ({vol_lookback}d)")
        self.vol_lookback = vol_lookback
    
    def get_weights(self, date: pd.Timestamp, price_data: pd.DataFrame,
                   current_weights: pd.Series, **kwargs) -> pd.Series:
        
        # Calculate volatilities
        try:
            end_idx = price_data.index.get_indexer([date], method='nearest')[0]
        except (KeyError, IndexError):
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        start_idx = max(0, end_idx - self.vol_lookback)
        
        if start_idx >= end_idx:
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        
        returns_data = price_data.iloc[start_idx:end_idx+1].pct_change().dropna()
        
        if len(returns_data) == 0:
            return pd.Series(1.0 / len(price_data.columns), index=price_data.columns)
        
        volatilities = returns_data.std()
        
        # Inverse volatility weighting
        inv_vol = 1.0 / volatilities
        weights = inv_vol / inv_vol.sum()
        
        return weights

class BacktestingEngine:
    """Advanced backtesting engine"""
    
    def __init__(self):
        self.strategies = {
            'equal_weight': EqualWeightStrategy(),
            'market_cap': MarketCapStrategy(),
            'momentum_90d': MomentumStrategy(90),
            'momentum_30d': MomentumStrategy(30),
            'mean_reversion': MeanReversionStrategy(30),
            'risk_parity': RiskParityStrategy(30)
        }
        
    def add_strategy(self, name: str, strategy: PortfolioStrategy):
        """Add custom strategy"""
        self.strategies[name] = strategy
        
    def run_backtest(self, price_data: pd.DataFrame, 
                    strategy: str,
                    config: BacktestConfig,
                    benchmark_data: Optional[pd.Series] = None) -> BacktestResult:
        """
        Run comprehensive backtest
        """
        
        if strategy not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        strategy_obj = self.strategies[strategy]
        
        # Prepare data
        start_date = pd.to_datetime(config.start_date)
        end_date = pd.to_datetime(config.end_date)
        
        # Filter price data to backtest period
        backtest_data = price_data.loc[start_date:end_date].copy()
        
        if len(backtest_data) < 30:
            raise ValueError("Insufficient data for backtesting")
        
        # Initialize tracking variables
        portfolio_values = []
        weights_history = []
        trades_history = []
        
        current_capital = config.initial_capital
        current_weights = pd.Series(0.0, index=backtest_data.columns)
        
        # Rebalancing dates
        rebal_dates = self._get_rebalancing_dates(backtest_data.index, config.rebalance_frequency)
        
        # Main backtesting loop
        last_rebal_date = None
        
        for date in backtest_data.index:
            
            # Check if rebalancing date
            if date in rebal_dates or last_rebal_date is None:
                
                # Get target weights from strategy
                target_weights = strategy_obj.get_weights(
                    date, backtest_data.loc[:date], current_weights
                )
                
                # Apply position size limits
                target_weights = self._apply_position_limits(target_weights, config.max_position_size)
                
                # Calculate trades needed
                trades = self._calculate_trades(
                    current_weights, target_weights, current_capital, 
                    backtest_data.loc[date], config.transaction_costs
                )
                
                # Execute trades and update positions
                if len(trades) > 0:
                    trades_summary = self._execute_trades(
                        trades, current_capital, config.transaction_costs
                    )
                    
                    # Record trades
                    for trade in trades:
                        trades_history.append({
                            'date': date,
                            'asset': trade['asset'],
                            'action': trade['action'],
                            'quantity': trade['quantity'],
                            'price': trade['price'],
                            'value': trade['value'],
                            'cost': trade['cost']
                        })
                    
                    # Update capital and weights after trades
                    current_capital -= trades_summary['total_cost']
                    current_weights = target_weights.copy()
                
                last_rebal_date = date
            
            # Calculate daily portfolio value (mark-to-market)
            if current_weights.sum() > 0:
                positions_value = (current_weights * current_capital * 
                                 backtest_data.loc[date] / backtest_data.loc[last_rebal_date]).sum()
            else:
                positions_value = current_capital
                
            portfolio_values.append({
                'date': date,
                'value': positions_value,
                'cash': current_capital * (1 - current_weights.sum()) if current_weights.sum() <= 1 else 0
            })
            
            weights_history.append(dict(current_weights))
        
        # Convert results to DataFrames
        portfolio_df = pd.DataFrame(portfolio_values).set_index('date')
        weights_df = pd.DataFrame(weights_history, index=backtest_data.index)
        trades_df = pd.DataFrame(trades_history)
        
        # Calculate performance metrics
        returns = portfolio_df['value'].pct_change().dropna()
        metrics = self._calculate_metrics(portfolio_df['value'], returns, config)
        
        # Benchmark comparison
        if benchmark_data is not None:
            benchmark_returns = benchmark_data.loc[start_date:end_date].pct_change().dropna()
        elif config.benchmark in backtest_data.columns:
            benchmark_returns = backtest_data[config.benchmark].pct_change().dropna()
        else:
            benchmark_returns = pd.Series(0.0, index=returns.index)
        
        benchmark_performance = (1 + benchmark_returns).cumprod() * config.initial_capital
        
        # Risk metrics
        risk_metrics = self._calculate_risk_metrics(returns, benchmark_returns, config)
        
        # Performance attribution
        attribution = self._calculate_attribution(weights_df, backtest_data, returns)
        
        # Monthly and annual returns
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        annual_returns = returns.resample('Y').apply(lambda x: (1 + x).prod() - 1)
        
        # Drawdowns
        rolling_max = portfolio_df['value'].expanding().max()
        drawdowns = (portfolio_df['value'] - rolling_max) / rolling_max
        
        # Summary
        summary = {
            'strategy_name': strategy_obj.name,
            'total_days': len(portfolio_df),
            'rebalancing_events': len(rebal_dates),
            'total_trades': len(trades_df),
            'final_value': portfolio_df['value'].iloc[-1],
            'total_return_pct': (portfolio_df['value'].iloc[-1] / config.initial_capital - 1) * 100,
            'benchmark_return_pct': (benchmark_performance.iloc[-1] / config.initial_capital - 1) * 100,
            'excess_return_pct': metrics['total_return'] - (benchmark_performance.iloc[-1] / config.initial_capital - 1),
            'total_transaction_costs': trades_df['cost'].sum() if len(trades_df) > 0 else 0
        }
        
        return BacktestResult(
            config=config,
            portfolio_value=portfolio_df['value'],
            weights_history=weights_df,
            trades_history=trades_df,
            metrics=metrics,
            benchmark_performance=benchmark_performance,
            monthly_returns=monthly_returns,
            annual_returns=annual_returns,
            drawdowns=drawdowns,
            risk_metrics=risk_metrics,
            attribution=attribution,
            summary=summary
        )
    
    def _get_rebalancing_dates(self, date_index: pd.DatetimeIndex, 
                              frequency: RebalanceFrequency) -> List[pd.Timestamp]:
        """Generate rebalancing dates"""
        
        start_date = date_index[0]
        end_date = date_index[-1]
        
        if frequency == RebalanceFrequency.DAILY:
            return list(date_index)
        elif frequency == RebalanceFrequency.WEEKLY:
            return list(pd.date_range(start_date, end_date, freq='W'))
        elif frequency == RebalanceFrequency.BIWEEKLY:
            return list(pd.date_range(start_date, end_date, freq='2W'))
        elif frequency == RebalanceFrequency.MONTHLY:
            return list(pd.date_range(start_date, end_date, freq='M'))
        elif frequency == RebalanceFrequency.QUARTERLY:
            return list(pd.date_range(start_date, end_date, freq='Q'))
        
        # Filter to actual trading days for non-daily frequencies
        rebal_dates = []
        if frequency != RebalanceFrequency.DAILY:
            # Get the theoretical dates first
            if frequency == RebalanceFrequency.WEEKLY:
                base_dates = pd.date_range(start_date, end_date, freq='W')
            elif frequency == RebalanceFrequency.BIWEEKLY:
                base_dates = pd.date_range(start_date, end_date, freq='2W')
            elif frequency == RebalanceFrequency.MONTHLY:
                base_dates = pd.date_range(start_date, end_date, freq='M')
            elif frequency == RebalanceFrequency.QUARTERLY:
                base_dates = pd.date_range(start_date, end_date, freq='Q')
            else:
                return list(date_index)
            
            for target_date in base_dates:
                # Find closest trading day
                closest_date = min(date_index, key=lambda x: abs((x - target_date).total_seconds()))
                rebal_dates.append(closest_date)
            
            return rebal_dates
        else:
            return list(date_index)
    
    def _apply_position_limits(self, weights: pd.Series, max_position: float) -> pd.Series:
        """Apply position size limits"""
        
        # Cap individual positions
        capped_weights = weights.clip(upper=max_position)
        
        # Renormalize if needed
        if capped_weights.sum() > 1.0:
            capped_weights = capped_weights / capped_weights.sum()
        
        return capped_weights
    
    def _calculate_trades(self, current_weights: pd.Series, target_weights: pd.Series,
                         current_capital: float, current_prices: pd.Series,
                         transaction_costs: TransactionCosts) -> List[Dict]:
        """Calculate required trades"""
        
        trades = []
        
        for asset in target_weights.index:
            current_weight = current_weights.get(asset, 0.0)
            target_weight = target_weights[asset]
            
            weight_diff = target_weight - current_weight
            trade_value = weight_diff * current_capital
            
            if abs(trade_value) > transaction_costs.min_trade_size:
                price = current_prices[asset]
                quantity = trade_value / price
                
                # Calculate transaction costs
                fee_rate = transaction_costs.taker_fee  # Assume taker for simplicity
                slippage_rate = transaction_costs.slippage_bps / 10000
                
                total_cost = abs(trade_value) * (fee_rate + slippage_rate)
                
                trades.append({
                    'asset': asset,
                    'action': 'buy' if weight_diff > 0 else 'sell',
                    'quantity': abs(quantity),
                    'price': price,
                    'value': abs(trade_value),
                    'cost': total_cost
                })
        
        return trades
    
    def _execute_trades(self, trades: List[Dict], current_capital: float,
                       transaction_costs: TransactionCosts) -> Dict:
        """Execute trades and return summary"""
        
        total_cost = sum(trade['cost'] for trade in trades)
        total_volume = sum(trade['value'] for trade in trades)
        
        return {
            'total_cost': total_cost,
            'total_volume': total_volume,
            'cost_ratio': total_cost / current_capital if current_capital > 0 else 0
        }
    
    def _calculate_metrics(self, portfolio_values: pd.Series, returns: pd.Series,
                          config: BacktestConfig) -> Dict[str, float]:
        """Calculate comprehensive performance metrics"""
        
        if len(returns) == 0:
            return {}
        
        total_return = (portfolio_values.iloc[-1] / config.initial_capital) - 1
        
        # Annualized return
        days = (portfolio_values.index[-1] - portfolio_values.index[0]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252)
        
        # Sharpe ratio
        excess_returns = returns - (config.risk_free_rate / 252)
        sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Drawdown metrics
        rolling_max = portfolio_values.expanding().max()
        drawdowns = (portfolio_values - rolling_max) / rolling_max
        max_drawdown = drawdowns.min()
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252)
        sortino_ratio = annualized_return / downside_deviation if downside_deviation > 0 else 0
        
        # Win rate
        win_rate = (returns > 0).mean()
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'sortino_ratio': sortino_ratio,
            'win_rate': win_rate,
            'best_day': returns.max(),
            'worst_day': returns.min(),
            'positive_days': (returns > 0).sum(),
            'negative_days': (returns < 0).sum(),
        }
    
    def _calculate_risk_metrics(self, returns: pd.Series, benchmark_returns: pd.Series,
                               config: BacktestConfig) -> Dict[str, float]:
        """Calculate advanced risk metrics"""
        
        risk_metrics = {}
        
        if len(returns) > 0:
            # VaR and CVaR
            risk_metrics['var_95'] = returns.quantile(0.05)
            risk_metrics['var_99'] = returns.quantile(0.01)
            
            var_95_level = returns.quantile(0.05)
            risk_metrics['cvar_95'] = returns[returns <= var_95_level].mean()
            
            # Beta vs benchmark
            if len(benchmark_returns) > 0 and len(returns) == len(benchmark_returns):
                covariance = returns.cov(benchmark_returns)
                benchmark_var = benchmark_returns.var()
                risk_metrics['beta'] = covariance / benchmark_var if benchmark_var > 0 else 0
                
                # Tracking error
                active_returns = returns - benchmark_returns
                risk_metrics['tracking_error'] = active_returns.std() * np.sqrt(252)
                risk_metrics['information_ratio'] = active_returns.mean() / active_returns.std() * np.sqrt(252) if active_returns.std() > 0 else 0
        
        return risk_metrics
    
    def _calculate_attribution(self, weights_df: pd.DataFrame, 
                              price_data: pd.DataFrame, returns: pd.Series) -> Dict:
        """Calculate performance attribution"""
        
        attribution = {
            'asset_contributions': {},
            'weight_changes': {},
            'return_decomposition': {}
        }
        
        # Asset contribution to portfolio return
        asset_returns = price_data.pct_change()
        
        for asset in weights_df.columns:
            if asset in asset_returns.columns:
                asset_weight = weights_df[asset].mean()  # Average weight over period
                asset_return = asset_returns[asset].mean() * 252  # Annualized
                attribution['asset_contributions'][asset] = asset_weight * asset_return
        
        # Weight changes over time
        for asset in weights_df.columns:
            weight_changes = weights_df[asset].diff().abs().mean()
            attribution['weight_changes'][asset] = weight_changes
        
        return attribution

    def compare_strategies(self, price_data: pd.DataFrame, 
                          strategies: List[str],
                          config: BacktestConfig) -> pd.DataFrame:
        """Compare multiple strategies"""
        
        results = {}
        
        for strategy in strategies:
            try:
                result = self.run_backtest(price_data, strategy, config)
                results[strategy] = result.metrics
            except Exception as e:
                logger.error(f"Failed to backtest {strategy}: {e}")
                continue
        
        # Create comparison DataFrame
        if results:
            comparison_df = pd.DataFrame(results).T
            
            # Add rankings
            for metric in ['annualized_return', 'sharpe_ratio', 'calmar_ratio']:
                if metric in comparison_df.columns:
                    comparison_df[f'{metric}_rank'] = comparison_df[metric].rank(ascending=False)
            
            return comparison_df
        
        return pd.DataFrame()

# Global backtesting engine instance  
backtesting_engine = BacktestingEngine()