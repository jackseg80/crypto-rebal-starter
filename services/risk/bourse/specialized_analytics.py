"""
Specialized Analytics for Bourse Portfolio

Features unique to stock market:
- Earnings predictor (dates, volatility, alerts)
- Sector rotation detector (clustering, signals)
- Beta forecaster (dynamic, rolling, multi-factor)
- Dividend analyzer (yield, ex-div dates, impact)
- Margin monitoring (CFDs, leverage, margin calls)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.stats import linregress

logger = logging.getLogger(__name__)


class SpecializedBourseAnalytics:
    """
    Specialized analytics for stock market portfolio management

    Features:
    - Earnings predictor with volatility forecasting
    - Sector rotation detection with clustering
    - Beta forecaster (dynamic, rolling, multi-factor)
    - Dividend analyzer with yield tracking
    - Margin monitoring for leveraged positions
    """

    def __init__(self):
        self.cache = {}

        # Sector mapping for common tickers
        self.sector_map = {
            # Tech
            'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
            'META': 'Technology', 'NVDA': 'Technology', 'TSLA': 'Technology', 'AMZN': 'Technology',
            'NFLX': 'Technology', 'AMD': 'Technology', 'INTC': 'Technology', 'CRM': 'Technology',
            'PLTR': 'Technology', 'COIN': 'Technology', 'CDR': 'Technology',  # Palantir, Coinbase, CD Projekt
            'IFX': 'Technology',  # Infineon (semiconductors)

            # Finance
            'JPM': 'Finance', 'BAC': 'Finance', 'WFC': 'Finance', 'GS': 'Finance',
            'MS': 'Finance', 'C': 'Finance', 'BLK': 'Finance', 'SCHW': 'Finance',
            'UBSG': 'Finance', 'BRKb': 'Finance', 'SLHn': 'Finance',  # UBS, Berkshire, Swiss Life (insurance)

            # Healthcare
            'JNJ': 'Healthcare', 'UNH': 'Healthcare', 'PFE': 'Healthcare', 'ABBV': 'Healthcare',
            'TMO': 'Healthcare', 'ABT': 'Healthcare', 'LLY': 'Healthcare', 'MRK': 'Healthcare',
            'BAX': 'Healthcare', 'ROG': 'Healthcare',  # Baxter, Roche

            # Consumer
            'WMT': 'Consumer', 'PG': 'Consumer', 'KO': 'Consumer', 'PEP': 'Consumer',
            'MCD': 'Consumer', 'NKE': 'Consumer', 'COST': 'Consumer', 'SBUX': 'Consumer',
            'UHRN': 'Consumer',  # Swatch Group (luxury goods)

            # Energy
            'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy',

            # Industrial
            'BA': 'Industrial', 'CAT': 'Industrial', 'GE': 'Industrial', 'MMM': 'Industrial',

            # ETFs
            'SPY': 'ETF-Broad', 'QQQ': 'ETF-Tech', 'IWM': 'ETF-SmallCap', 'DIA': 'ETF-Industrial',
            'VTI': 'ETF-Broad', 'VOO': 'ETF-Broad', 'EFA': 'ETF-International', 'EEM': 'ETF-Emerging',
            'AGG': 'ETF-Bonds', 'TLT': 'ETF-Bonds', 'IWDA': 'ETF-International', 'CSPX': 'ETF-Broad',
            'ITEK': 'ETF-Tech',  # HAN-GINS Tech Megatrend
        }

    # ==================== Earnings Predictor ====================

    def predict_earnings_impact(
        self,
        ticker: str,
        price_history: pd.DataFrame,
        earnings_dates: Optional[List[datetime]] = None
    ) -> Dict[str, Any]:
        """
        Predict earnings impact on volatility

        Args:
            ticker: Stock ticker
            price_history: Historical OHLCV data
            earnings_dates: List of known earnings dates (optional)

        Returns:
            Dict with earnings predictions:
            {
                'ticker': str,
                'next_earnings_date': datetime or None,
                'days_until_earnings': int,
                'pre_earnings_vol': float,
                'post_earnings_vol': float,
                'vol_increase_pct': float,
                'avg_post_earnings_move': float,
                'alert_level': str ('high' | 'medium' | 'low'),
                'recommendation': str
            }
        """
        try:
            # Calculate returns
            returns = price_history['close'].pct_change().dropna()

            if earnings_dates:
                # Analyze historical earnings volatility
                pre_earnings_vols = []
                post_earnings_vols = []
                post_earnings_moves = []

                for earnings_date in earnings_dates:
                    # Convert to pandas Timestamp for comparison
                    earnings_ts = pd.Timestamp(earnings_date)

                    # Find closest date in price_history
                    idx = price_history.index.get_indexer([earnings_ts], method='nearest')[0]

                    if idx < 5 or idx >= len(price_history) - 5:
                        continue

                    # Pre-earnings volatility (5 days before)
                    pre_returns = returns.iloc[idx-5:idx]
                    pre_vol = pre_returns.std() * np.sqrt(252)
                    pre_earnings_vols.append(pre_vol)

                    # Post-earnings volatility (5 days after)
                    post_returns = returns.iloc[idx:idx+5]
                    post_vol = post_returns.std() * np.sqrt(252)
                    post_earnings_vols.append(post_vol)

                    # Immediate move (day of earnings)
                    if idx < len(returns):
                        post_earnings_moves.append(abs(returns.iloc[idx]))

                avg_pre_vol = np.mean(pre_earnings_vols) if pre_earnings_vols else 0
                avg_post_vol = np.mean(post_earnings_vols) if post_earnings_vols else 0
                vol_increase = ((avg_post_vol - avg_pre_vol) / avg_pre_vol * 100) if avg_pre_vol > 0 else 0
                avg_move = np.mean(post_earnings_moves) if post_earnings_moves else 0

                # Next earnings date (assume quarterly)
                next_earnings = earnings_dates[-1] + timedelta(days=90) if earnings_dates else None
                days_until = (next_earnings - datetime.now()).days if next_earnings else None

                # Alert level
                if days_until and days_until <= 7:
                    alert_level = 'high'
                    recommendation = f"Reduce position size - earnings in {days_until} days"
                elif days_until and days_until <= 14:
                    alert_level = 'medium'
                    recommendation = f"Monitor closely - earnings in {days_until} days"
                else:
                    alert_level = 'low'
                    recommendation = "Normal monitoring"

            else:
                # No earnings dates provided - use generic volatility analysis
                current_vol = returns.std() * np.sqrt(252)
                avg_pre_vol = current_vol
                avg_post_vol = current_vol * 1.5  # Assume 50% increase
                vol_increase = 50.0
                avg_move = returns.abs().mean()
                next_earnings = None
                days_until = None
                alert_level = 'low'
                recommendation = "No earnings dates available - using generic estimates"

            result = {
                'ticker': ticker,
                'next_earnings_date': next_earnings.isoformat() if next_earnings else None,
                'days_until_earnings': days_until,
                'pre_earnings_vol': float(avg_pre_vol),
                'post_earnings_vol': float(avg_post_vol),
                'vol_increase_pct': float(vol_increase),
                'avg_post_earnings_move': float(avg_move * 100),  # Convert to percentage
                'alert_level': alert_level,
                'recommendation': recommendation,
                'num_earnings_analyzed': len(earnings_dates) if earnings_dates else 0,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Earnings prediction for {ticker}: alert={alert_level}, vol_increase={vol_increase:.1f}%")
            return result

        except Exception as e:
            logger.error(f"Error predicting earnings impact for {ticker}: {e}")
            raise

    # ==================== Sector Rotation Detector ====================

    def detect_sector_rotation(
        self,
        positions_returns: Dict[str, pd.Series],
        lookback_days: int = 60
    ) -> Dict[str, Any]:
        """
        Detect sector rotation patterns

        Args:
            positions_returns: Dict of {ticker: returns_series}
            lookback_days: Days to analyze for rotation

        Returns:
            Dict with sector rotation analysis:
            {
                'sectors': {sector: {'return': x, 'volatility': y, 'sharpe': z, 'signal': str}},
                'rotation_detected': bool,
                'hot_sectors': List[str],
                'cold_sectors': List[str],
                'recommendations': List[str],
                'clustering': Dict with hierarchical clustering
            }
        """
        try:
            # Map tickers to sectors
            ticker_sectors = {}
            for ticker in positions_returns.keys():
                ticker_sectors[ticker] = self.sector_map.get(ticker, 'Other')

            # Align returns to common dates
            returns_df = pd.DataFrame(positions_returns)
            returns_df = returns_df.dropna()

            # Limit to lookback period
            if len(returns_df) > lookback_days:
                returns_df = returns_df.tail(lookback_days)

            # Calculate sector-level metrics
            sector_metrics = {}
            sector_returns = {}

            for sector in set(ticker_sectors.values()):
                # Get tickers in this sector
                sector_tickers = [t for t, s in ticker_sectors.items() if s == sector]

                if not sector_tickers:
                    continue

                # Equal-weight sector return
                sector_ret = returns_df[sector_tickers].mean(axis=1)
                sector_returns[sector] = sector_ret

                # Metrics
                total_return = (1 + sector_ret).prod() - 1
                volatility = sector_ret.std() * np.sqrt(252)
                sharpe = (sector_ret.mean() * 252) / volatility if volatility > 0 else 0

                sector_metrics[sector] = {
                    'return': float(total_return * 100),  # Percentage
                    'annualized_return': float(sector_ret.mean() * 252 * 100),
                    'volatility': float(volatility * 100),
                    'sharpe_ratio': float(sharpe),
                    'num_positions': len(sector_tickers)
                }

            # Detect rotation (compare recent vs full period)
            recent_window = lookback_days // 3  # Last 1/3 of period

            sector_momentum = {}
            for sector, metrics in sector_metrics.items():
                if sector not in sector_returns:
                    continue

                full_return = sector_returns[sector].mean()
                recent_return = sector_returns[sector].tail(recent_window).mean()

                # Momentum = recent return / full period return
                # FIX: Avoid division by very small numbers (< 0.1% daily return = 25% annualized)
                MIN_RETURN_THRESHOLD = 0.001  # 0.1% daily = 25% annualized

                if abs(full_return) < MIN_RETURN_THRESHOLD:
                    # For sectors with near-zero returns, use absolute difference instead of ratio
                    momentum = 1.0 + (recent_return - full_return) * 100  # Scale by 100 to match ratio scale
                else:
                    # Normal case: ratio of recent vs full period
                    momentum = (recent_return / full_return) if full_return != 0 else 1.0

                # Cap momentum to prevent extreme values
                momentum = max(-5.0, min(5.0, momentum))

                sector_momentum[sector] = momentum

            # Classify sectors
            momentum_threshold_high = 1.2  # 20% outperformance
            momentum_threshold_low = 0.8   # 20% underperformance

            hot_sectors = [s for s, m in sector_momentum.items() if m > momentum_threshold_high]
            cold_sectors = [s for s, m in sector_momentum.items() if m < momentum_threshold_low]

            # Add signals
            for sector in sector_metrics.keys():
                momentum = sector_momentum.get(sector, 1.0)

                if momentum > momentum_threshold_high:
                    sector_metrics[sector]['signal'] = 'overweight'
                    sector_metrics[sector]['momentum'] = float(momentum)
                elif momentum < momentum_threshold_low:
                    sector_metrics[sector]['signal'] = 'underweight'
                    sector_metrics[sector]['momentum'] = float(momentum)
                else:
                    sector_metrics[sector]['signal'] = 'neutral'
                    sector_metrics[sector]['momentum'] = float(momentum)

            # Recommendations
            recommendations = []
            for sector in hot_sectors:
                recommendations.append(f"Consider overweighting {sector} (strong momentum)")
            for sector in cold_sectors:
                recommendations.append(f"Consider underweighting {sector} (weak momentum)")

            # Hierarchical clustering
            if len(sector_returns) >= 2:
                sector_returns_df = pd.DataFrame(sector_returns)
                sector_corr = sector_returns_df.corr()

                distance_matrix = 1 - sector_corr.abs()
                linkage_matrix = linkage(distance_matrix.values[np.triu_indices_from(distance_matrix.values, k=1)], method='ward')

                clustering = {
                    'linkage_matrix': linkage_matrix.tolist(),
                    'labels': list(sector_returns_df.columns),
                    'method': 'ward'
                }
            else:
                clustering = None

            rotation_detected = len(hot_sectors) > 0 or len(cold_sectors) > 0

            result = {
                'sectors': sector_metrics,
                'rotation_detected': rotation_detected,
                'hot_sectors': hot_sectors,
                'cold_sectors': cold_sectors,
                'recommendations': recommendations,
                'clustering': clustering,
                'lookback_days': lookback_days,
                'num_sectors': len(sector_metrics),
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Sector rotation analysis: {len(hot_sectors)} hot, {len(cold_sectors)} cold sectors")
            return result

        except Exception as e:
            logger.error(f"Error detecting sector rotation: {e}")
            raise

    # ==================== Beta Forecaster ====================

    def forecast_beta(
        self,
        position_returns: pd.Series,
        benchmark_returns: pd.Series,
        forecast_method: str = 'ewma',
        rolling_window: int = 60
    ) -> Dict[str, Any]:
        """
        Forecast dynamic beta vs benchmark

        Args:
            position_returns: Asset returns
            benchmark_returns: Benchmark returns
            forecast_method: 'ewma' | 'rolling' | 'expanding'
            rolling_window: Window for rolling calculations

        Returns:
            Dict with beta forecast:
            {
                'current_beta': float,
                'forecasted_beta': float,
                'beta_trend': str ('increasing' | 'decreasing' | 'stable'),
                'rolling_betas': List[float],
                'r_squared': float,
                'alpha': float,
                'volatility_ratio': float
            }
        """
        try:
            # Align returns
            aligned = pd.DataFrame({
                'position': position_returns,
                'benchmark': benchmark_returns
            }).dropna()

            if len(aligned) < 30:
                raise ValueError(f"Insufficient data: only {len(aligned)} days")

            # Current beta (full period)
            slope, intercept, r_value, p_value, std_err = linregress(
                aligned['benchmark'], aligned['position']
            )
            current_beta = float(slope)
            alpha = float(intercept)
            r_squared = float(r_value ** 2)

            # Rolling beta
            rolling_betas = []
            for i in range(rolling_window, len(aligned)):
                window_data = aligned.iloc[i-rolling_window:i]
                slope, _, _, _, _ = linregress(window_data['benchmark'], window_data['position'])
                rolling_betas.append(float(slope))

            # Forecast based on method
            if forecast_method == 'ewma':
                # Exponentially weighted moving average (more weight on recent)
                span = 20  # ~1 month
                ewma_betas = pd.Series(rolling_betas).ewm(span=span).mean()
                forecasted_beta = float(ewma_betas.iloc[-1]) if len(ewma_betas) > 0 else current_beta

            elif forecast_method == 'rolling':
                # Simple moving average
                forecasted_beta = float(np.mean(rolling_betas[-10:])) if len(rolling_betas) >= 10 else current_beta

            else:  # expanding
                forecasted_beta = current_beta

            # Beta trend
            if len(rolling_betas) >= 10:
                recent_trend = np.mean(rolling_betas[-5:]) - np.mean(rolling_betas[-10:-5])
                if recent_trend > 0.1:
                    beta_trend = 'increasing'
                elif recent_trend < -0.1:
                    beta_trend = 'decreasing'
                else:
                    beta_trend = 'stable'
            else:
                beta_trend = 'stable'

            # Volatility ratio (position vol / benchmark vol)
            vol_position = aligned['position'].std() * np.sqrt(252)
            vol_benchmark = aligned['benchmark'].std() * np.sqrt(252)
            vol_ratio = float(vol_position / vol_benchmark) if vol_benchmark > 0 else 1.0

            result = {
                'current_beta': current_beta,
                'forecasted_beta': forecasted_beta,
                'beta_trend': beta_trend,
                'rolling_betas': rolling_betas[-30:],  # Last 30 days
                'r_squared': r_squared,
                'alpha': alpha * 252 * 100,  # Annualized alpha in %
                'volatility_ratio': vol_ratio,
                'forecast_method': forecast_method,
                'rolling_window': rolling_window,
                'observation_days': len(aligned),
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Beta forecast: current={current_beta:.2f}, forecast={forecasted_beta:.2f}, trend={beta_trend}")
            return result

        except Exception as e:
            logger.error(f"Error forecasting beta: {e}")
            raise

    # ==================== Dividend Analyzer ====================

    def analyze_dividends(
        self,
        ticker: str,
        price_history: pd.DataFrame,
        dividends: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Analyze dividend impact and yield

        Args:
            ticker: Stock ticker
            price_history: Historical OHLCV data with 'adjusted_close'
            dividends: Dividend payment series (optional, from yfinance)

        Returns:
            Dict with dividend analysis:
            {
                'ticker': str,
                'current_yield': float,
                'annual_dividend': float,
                'payout_frequency': str,
                'next_ex_dividend_date': datetime or None,
                'days_until_ex_dividend': int,
                'avg_price_drop_ex_div': float,
                'total_dividends_12m': float,
                'dividend_growth_rate': float
            }
        """
        try:
            # Handle case-insensitive column names (yfinance uses 'Close', we use 'close')
            if 'close' in price_history.columns:
                current_price = float(price_history['close'].iloc[-1])
            elif 'Close' in price_history.columns:
                current_price = float(price_history['Close'].iloc[-1])
            else:
                raise ValueError(f"No 'close' or 'Close' column found in price_history. Available columns: {list(price_history.columns)}")

            if dividends is not None and len(dividends) > 0:
                # Real dividend data
                dividends_12m = dividends[dividends.index > (datetime.now() - timedelta(days=365))]
                annual_dividend = float(dividends_12m.sum())

                # Current yield
                current_yield = (annual_dividend / current_price * 100) if current_price > 0 else 0

                # Payout frequency
                num_payments = len(dividends_12m)
                if num_payments >= 4:
                    payout_frequency = 'quarterly'
                elif num_payments >= 2:
                    payout_frequency = 'semi-annual'
                elif num_payments >= 1:
                    payout_frequency = 'annual'
                else:
                    payout_frequency = 'irregular'

                # Next ex-dividend date (estimate based on last payment)
                if len(dividends) > 0:
                    last_div_date = dividends.index[-1]

                    if payout_frequency == 'quarterly':
                        next_ex_div = last_div_date + timedelta(days=90)
                    elif payout_frequency == 'semi-annual':
                        next_ex_div = last_div_date + timedelta(days=180)
                    elif payout_frequency == 'annual':
                        next_ex_div = last_div_date + timedelta(days=365)
                    else:
                        next_ex_div = None

                    days_until = (next_ex_div - datetime.now()).days if next_ex_div else None
                else:
                    next_ex_div = None
                    days_until = None

                # Average price drop on ex-dividend day
                # (Simplified: assume drop ≈ dividend amount)
                avg_div_payment = annual_dividend / num_payments if num_payments > 0 else 0
                avg_price_drop = (avg_div_payment / current_price * 100) if current_price > 0 else 0

                # Dividend growth rate (YoY)
                if len(dividends) >= 2:
                    dividends_sorted = dividends.sort_index()
                    recent_year_div = dividends_sorted[dividends_sorted.index > (datetime.now() - timedelta(days=365))].sum()
                    prev_year_div = dividends_sorted[
                        (dividends_sorted.index > (datetime.now() - timedelta(days=730))) &
                        (dividends_sorted.index <= (datetime.now() - timedelta(days=365)))
                    ].sum()

                    dividend_growth = ((recent_year_div - prev_year_div) / prev_year_div * 100) if prev_year_div > 0 else 0
                else:
                    dividend_growth = 0

            else:
                # No dividend data - estimate from adjusted vs close price
                # (Adjusted price accounts for dividends)
                current_yield = 0.0
                annual_dividend = 0.0
                payout_frequency = 'none'
                next_ex_div = None
                days_until = None
                avg_price_drop = 0.0
                dividend_growth = 0.0

            result = {
                'ticker': ticker,
                'current_yield': float(current_yield),
                'annual_dividend': float(annual_dividend),
                'payout_frequency': payout_frequency,
                'next_ex_dividend_date': next_ex_div.isoformat() if next_ex_div else None,
                'days_until_ex_dividend': days_until,
                'avg_price_drop_ex_div': float(avg_price_drop),
                'total_dividends_12m': float(annual_dividend),
                'dividend_growth_rate': float(dividend_growth),
                'has_dividend_data': dividends is not None and len(dividends) > 0,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Dividend analysis for {ticker}: yield={current_yield:.2f}%, frequency={payout_frequency}")
            return result

        except Exception as e:
            logger.error(f"Error analyzing dividends for {ticker}: {e}")
            raise

    # ==================== Margin Monitoring ====================

    def monitor_margin(
        self,
        positions: List[Dict[str, Any]],
        account_equity: float,
        maintenance_margin_pct: float = 0.25,
        initial_margin_pct: float = 0.50
    ) -> Dict[str, Any]:
        """
        Monitor margin requirements for leveraged positions (CFDs)

        Args:
            positions: List of positions with 'market_value_usd', 'leverage' (optional)
            account_equity: Total account equity
            maintenance_margin_pct: Maintenance margin requirement (default 25%)
            initial_margin_pct: Initial margin requirement (default 50%)

        Returns:
            Dict with margin analysis:
            {
                'account_equity': float,
                'total_exposure': float,
                'total_margin_used': float,
                'margin_utilization': float,
                'available_margin': float,
                'margin_call_distance': float,
                'current_leverage': float,
                'optimal_leverage': float,
                'warnings': List[str],
                'recommendations': List[str]
            }
        """
        try:
            total_exposure = 0.0
            total_margin_used = 0.0

            for pos in positions:
                market_value = pos.get('market_value_usd', 0)
                leverage = pos.get('leverage', 1.0)  # Default 1x (no leverage)

                exposure = market_value * leverage

                # Margin calculation:
                # - Cash account (leverage = 1.0): no margin used
                # - Leveraged account (leverage > 1.0): margin = value * (1 - 1/leverage)
                if leverage > 1.0:
                    margin_required = market_value * (1 - 1/leverage)
                else:
                    margin_required = 0.0  # No margin for cash accounts

                total_exposure += exposure
                total_margin_used += margin_required

            # Margin utilization (as ratio 0.0-1.0, not percentage)
            margin_utilization = (total_margin_used / account_equity) if account_equity > 0 else 0
            available_margin = max(0, account_equity - total_margin_used)

            # Current leverage
            current_leverage = (total_exposure / account_equity) if account_equity > 0 else 0

            # Margin call distance (as ratio 0.0-1.0, not percentage)
            # Margin call occurs when equity falls below maintenance margin
            maintenance_margin_required = total_exposure * maintenance_margin_pct
            margin_call_distance = ((account_equity - maintenance_margin_required) / account_equity) if account_equity > 0 else 0

            # Optimal leverage (conservative: target 50% margin utilization)
            target_margin_utilization = 0.50
            optimal_leverage = (account_equity * target_margin_utilization / total_margin_used * current_leverage) if total_margin_used > 0 else 1.0
            optimal_leverage = max(1.0, min(optimal_leverage, 5.0))  # Cap between 1x-5x

            # Warnings
            warnings = []
            recommendations = []

            if margin_utilization > 0.80:
                warnings.append("CRITICAL: Margin utilization above 80% - high risk of margin call")
                recommendations.append("Reduce position sizes or add equity immediately")
            elif margin_utilization > 0.60:
                warnings.append("WARNING: Margin utilization above 60% - moderate risk")
                recommendations.append("Consider reducing leverage or adding equity")

            if margin_call_distance < 0.10:
                warnings.append("CRITICAL: Margin call distance below 10% - extremely high risk")
                recommendations.append("Close positions or add equity immediately")
            elif margin_call_distance < 0.20:
                warnings.append("WARNING: Margin call distance below 20% - high risk")
                recommendations.append("Monitor closely and prepare to reduce exposure")

            if current_leverage > 3.0:
                warnings.append(f"High leverage detected: {current_leverage:.1f}x")
                recommendations.append(f"Consider reducing to optimal leverage: {optimal_leverage:.1f}x")

            result = {
                'account_equity': float(account_equity),
                'total_exposure': float(total_exposure),
                'total_margin_used': float(total_margin_used),
                'margin_utilization': float(margin_utilization),
                'available_margin': float(available_margin),
                'margin_call_distance': float(margin_call_distance),
                'current_leverage': float(current_leverage),
                'optimal_leverage': float(optimal_leverage),
                'maintenance_margin_pct': float(maintenance_margin_pct * 100),
                'initial_margin_pct': float(initial_margin_pct * 100),
                'num_positions': len(positions),
                'warnings': warnings,
                'recommendations': recommendations,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Margin monitoring: utilization={margin_utilization:.1f}%, leverage={current_leverage:.1f}x, {len(warnings)} warnings")
            return result

        except Exception as e:
            logger.error(f"Error monitoring margin: {e}")
            raise
