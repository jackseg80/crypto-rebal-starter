"""
Multi-Asset Class Portfolio Management
Supports crypto, stocks, bonds, commodities, and REITs
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import yfinance as yf
import logging
from datetime import datetime, timedelta
import requests
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class AssetClass(Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    BOND = "bond"
    COMMODITY = "commodity"
    REIT = "reit"
    FOREX = "forex"
    ETF = "etf"

@dataclass
class Asset:
    symbol: str
    name: str
    asset_class: AssetClass
    sector: Optional[str] = None
    region: Optional[str] = None
    currency: str = "USD"
    market_cap: Optional[float] = None
    expense_ratio: Optional[float] = None  # For ETFs
    yield_rate: Optional[float] = None     # For bonds/REITs
    beta: Optional[float] = None           # vs market benchmark
    
    def __post_init__(self):
        if isinstance(self.asset_class, str):
            self.asset_class = AssetClass(self.asset_class)

@dataclass
class AssetAllocation:
    target_allocation: Dict[AssetClass, float]  # Target % by asset class
    max_allocation: Dict[AssetClass, float]     # Maximum % by asset class
    min_allocation: Dict[AssetClass, float]     # Minimum % by asset class
    rebalance_threshold: float = 0.05           # 5% drift threshold

class MultiAssetManager:
    def __init__(self, cache_dir: str = "cache/multi_asset"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Asset universe
        self.assets: Dict[str, Asset] = {}
        self.price_cache: Dict[str, pd.DataFrame] = {}
        
        # Data sources configuration
        self.data_sources = {
            AssetClass.CRYPTO: self._fetch_crypto_prices,
            AssetClass.STOCK: self._fetch_stock_prices,
            AssetClass.BOND: self._fetch_bond_prices,
            AssetClass.COMMODITY: self._fetch_commodity_prices,
            AssetClass.REIT: self._fetch_reit_prices,
            AssetClass.ETF: self._fetch_etf_prices,
            AssetClass.FOREX: self._fetch_forex_prices
        }
        
        self._initialize_default_assets()

    def _initialize_default_assets(self):
        """Initialize with common assets across all classes"""
        
        # Major Cryptocurrencies
        crypto_assets = [
            Asset("BTC", "Bitcoin", AssetClass.CRYPTO, sector="Digital Currency"),
            Asset("ETH", "Ethereum", AssetClass.CRYPTO, sector="Smart Contract Platform"),
            Asset("BNB", "Binance Coin", AssetClass.CRYPTO, sector="Exchange Token"),
            Asset("ADA", "Cardano", AssetClass.CRYPTO, sector="Smart Contract Platform"),
            Asset("DOT", "Polkadot", AssetClass.CRYPTO, sector="Interoperability"),
            Asset("AVAX", "Avalanche", AssetClass.CRYPTO, sector="Smart Contract Platform"),
        ]
        
        # Major Stock Indices & Individual Stocks
        stock_assets = [
            Asset("SPY", "SPDR S&P 500 ETF", AssetClass.ETF, sector="Large Cap Blend", region="US"),
            Asset("QQQ", "Invesco QQQ Trust", AssetClass.ETF, sector="Technology", region="US"),
            Asset("VTI", "Vanguard Total Stock Market", AssetClass.ETF, sector="Total Market", region="US"),
            Asset("VXUS", "Vanguard Total International Stock", AssetClass.ETF, sector="International", region="Global"),
            Asset("AAPL", "Apple Inc.", AssetClass.STOCK, sector="Technology", region="US"),
            Asset("GOOGL", "Alphabet Inc.", AssetClass.STOCK, sector="Technology", region="US"),
            Asset("MSFT", "Microsoft Corporation", AssetClass.STOCK, sector="Technology", region="US"),
            Asset("AMZN", "Amazon.com Inc.", AssetClass.STOCK, sector="Consumer Discretionary", region="US"),
            Asset("TSLA", "Tesla Inc.", AssetClass.STOCK, sector="Consumer Discretionary", region="US"),
        ]
        
        # Bond ETFs
        bond_assets = [
            Asset("AGG", "iShares Core U.S. Aggregate Bond", AssetClass.ETF, sector="Aggregate Bond", yield_rate=0.025),
            Asset("TLT", "iShares 20+ Year Treasury Bond", AssetClass.ETF, sector="Long Treasury", yield_rate=0.03),
            Asset("IEF", "iShares 7-10 Year Treasury Bond", AssetClass.ETF, sector="Intermediate Treasury", yield_rate=0.028),
            Asset("HYG", "iShares iBoxx $ High Yield Corporate", AssetClass.ETF, sector="High Yield", yield_rate=0.05),
            Asset("VCIT", "Vanguard Intermediate-Term Corporate", AssetClass.ETF, sector="Corporate Bond", yield_rate=0.035),
            Asset("VTEB", "Vanguard Tax-Exempt Bond", AssetClass.ETF, sector="Municipal Bond", yield_rate=0.025),
        ]
        
        # Commodity ETFs
        commodity_assets = [
            Asset("GLD", "SPDR Gold Shares", AssetClass.ETF, sector="Gold"),
            Asset("SLV", "iShares Silver Trust", AssetClass.ETF, sector="Silver"),
            Asset("DBC", "Invesco DB Commodity Index", AssetClass.ETF, sector="Broad Commodities"),
            Asset("USO", "United States Oil Fund", AssetClass.ETF, sector="Oil"),
            Asset("UNG", "United States Natural Gas Fund", AssetClass.ETF, sector="Natural Gas"),
            Asset("PDBC", "Invesco Optimum Yield Diversified Commodity", AssetClass.ETF, sector="Broad Commodities"),
        ]
        
        # REIT ETFs
        reit_assets = [
            Asset("VNQ", "Vanguard Real Estate Index Fund", AssetClass.ETF, sector="REITs", yield_rate=0.035),
            Asset("SCHH", "Schwab U.S. REIT ETF", AssetClass.ETF, sector="REITs", yield_rate=0.033),
            Asset("VNQI", "Vanguard Global ex-U.S. Real Estate", AssetClass.ETF, sector="International REITs", yield_rate=0.04),
            Asset("REM", "iShares Mortgage Real Estate ETF", AssetClass.ETF, sector="Mortgage REITs", yield_rate=0.08),
        ]
        
        # Add all assets to the universe
        for asset_list in [crypto_assets, stock_assets, bond_assets, commodity_assets, reit_assets]:
            for asset in asset_list:
                self.assets[asset.symbol] = asset

    def add_asset(self, asset: Asset) -> None:
        """Add a new asset to the universe"""
        self.assets[asset.symbol] = asset
        logger.info(f"Added {asset.asset_class.value} asset: {asset.symbol} ({asset.name})")

    def get_assets_by_class(self, asset_class: AssetClass) -> List[Asset]:
        """Get all assets of a specific class"""
        return [asset for asset in self.assets.values() if asset.asset_class == asset_class]

    async def fetch_prices(self, symbols: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
        """Fetch price data for multiple assets across different classes"""
        
        results = {}
        
        # Group symbols by asset class for efficient fetching
        by_class = {}
        for symbol in symbols:
            if symbol not in self.assets:
                logger.warning(f"Asset {symbol} not found in universe")
                continue
                
            asset = self.assets[symbol]
            if asset.asset_class not in by_class:
                by_class[asset.asset_class] = []
            by_class[asset.asset_class].append(symbol)
        
        # Fetch prices by asset class
        for asset_class, class_symbols in by_class.items():
            try:
                fetcher = self.data_sources[asset_class]
                class_results = await fetcher(class_symbols, period)
                results.update(class_results)
                
            except Exception as e:
                logger.error(f"Failed to fetch {asset_class.value} prices: {e}")
                continue
        
        return results

    async def _fetch_crypto_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch cryptocurrency prices from existing crypto API"""
        
        results = {}
        
        # Use existing price history service
        from services.price_history import get_cached_history
        
        for symbol in symbols:
            try:
                # Convert period to days
                days = self._period_to_days(period)
                price_data = get_cached_history(symbol, days=days)
                
                if price_data:
                    # Convert to DataFrame
                    timestamps = [pd.to_datetime(p[0], unit='s') for p in price_data]
                    prices = [p[1] for p in price_data]
                    
                    df = pd.DataFrame({
                        'timestamp': timestamps,
                        'close': prices,
                        'symbol': symbol
                    }).set_index('timestamp')
                    
                    results[symbol] = df
                    
            except Exception as e:
                logger.error(f"Failed to fetch crypto price for {symbol}: {e}")
                continue
        
        return results

    async def _fetch_stock_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch stock prices using yfinance"""
        
        try:
            # Fetch data for all symbols at once
            tickers = yf.Tickers(' '.join(symbols))
            
            results = {}
            for symbol in symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    hist = ticker.history(period=period)
                    
                    if not hist.empty:
                        df = pd.DataFrame({
                            'close': hist['Close'],
                            'volume': hist['Volume'],
                            'symbol': symbol
                        })
                        results[symbol] = df
                        
                        # Cache the result
                        self._cache_price_data(symbol, df)
                        
                except Exception as e:
                    logger.error(f"Failed to fetch stock price for {symbol}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to fetch stock prices: {e}")
            return {}

    async def _fetch_bond_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch bond ETF prices using yfinance"""
        return await self._fetch_stock_prices(symbols, period)  # Same API

    async def _fetch_commodity_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch commodity ETF prices using yfinance"""
        return await self._fetch_stock_prices(symbols, period)  # Same API

    async def _fetch_reit_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch REIT prices using yfinance"""
        return await self._fetch_stock_prices(symbols, period)  # Same API

    async def _fetch_etf_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch ETF prices using yfinance"""
        return await self._fetch_stock_prices(symbols, period)  # Same API

    async def _fetch_forex_prices(self, symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
        """Fetch forex prices using yfinance"""
        # Add '=X' suffix for forex pairs if not present
        forex_symbols = []
        for symbol in symbols:
            if not symbol.endswith('=X'):
                forex_symbols.append(f"{symbol}=X")
            else:
                forex_symbols.append(symbol)
        
        return await self._fetch_stock_prices(forex_symbols, period)

    def calculate_multi_asset_correlation(self, price_data: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, Dict[AssetClass, Dict[AssetClass, float]]]:
        """Calculate correlation matrix with asset class breakdown"""
        
        if not price_data:
            return pd.DataFrame(), {}
        
        # Align all price data to common dates
        aligned_prices = {}
        common_dates = None
        
        for symbol, df in price_data.items():
            if 'close' in df.columns:
                prices = df['close'].dropna()
                if common_dates is None:
                    common_dates = prices.index
                else:
                    common_dates = common_dates.intersection(prices.index)
                aligned_prices[symbol] = prices
        
        if not aligned_prices or common_dates.empty:
            return pd.DataFrame(), {}
        
        # Create aligned price matrix
        price_matrix = pd.DataFrame(index=common_dates)
        for symbol, prices in aligned_prices.items():
            price_matrix[symbol] = prices.reindex(common_dates)
        
        # Calculate returns
        returns = price_matrix.pct_change().dropna()
        
        # Overall correlation matrix
        correlation_matrix = returns.corr()
        
        # Asset class correlation analysis
        class_correlations = {}
        for class1 in AssetClass:
            class1_symbols = [s for s in returns.columns if s in self.assets and self.assets[s].asset_class == class1]
            if not class1_symbols:
                continue
                
            class_correlations[class1] = {}
            
            for class2 in AssetClass:
                class2_symbols = [s for s in returns.columns if s in self.assets and self.assets[s].asset_class == class2]
                if not class2_symbols:
                    continue
                
                # Average correlation between asset classes
                correlations = []
                for s1 in class1_symbols:
                    for s2 in class2_symbols:
                        if s1 != s2 and s1 in correlation_matrix.index and s2 in correlation_matrix.columns:
                            correlations.append(correlation_matrix.loc[s1, s2])
                
                if correlations:
                    class_correlations[class1][class2] = np.mean(correlations)
                else:
                    class_correlations[class1][class2] = 0.0
        
        return correlation_matrix, class_correlations

    def analyze_asset_class_performance(self, price_data: Dict[str, pd.DataFrame], period_days: int = 252) -> Dict[AssetClass, Dict[str, float]]:
        """Analyze performance metrics by asset class"""
        
        performance_by_class = {}
        
        for asset_class in AssetClass:
            class_symbols = [s for s in price_data.keys() if s in self.assets and self.assets[s].asset_class == asset_class]
            if not class_symbols:
                continue
            
            class_metrics = {
                'total_return': [],
                'volatility': [],
                'sharpe_ratio': [],
                'max_drawdown': [],
                'symbols': class_symbols
            }
            
            for symbol in class_symbols:
                try:
                    df = price_data[symbol]
                    if 'close' not in df.columns or df.empty:
                        continue
                    
                    prices = df['close'].dropna()
                    returns = prices.pct_change().dropna()
                    
                    if len(returns) < 30:  # Need minimum data
                        continue
                    
                    # Calculate metrics
                    total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
                    volatility = returns.std() * np.sqrt(252) * 100  # Annualized
                    
                    # Sharpe ratio (assuming 2% risk-free rate)
                    risk_free_rate = 0.02
                    excess_returns = returns.mean() * 252 - risk_free_rate
                    sharpe_ratio = excess_returns / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
                    
                    # Maximum drawdown
                    cumulative = (1 + returns).cumprod()
                    running_max = cumulative.expanding().max()
                    drawdown = (cumulative - running_max) / running_max
                    max_drawdown = abs(drawdown.min()) * 100
                    
                    class_metrics['total_return'].append(total_return)
                    class_metrics['volatility'].append(volatility)
                    class_metrics['sharpe_ratio'].append(sharpe_ratio)
                    class_metrics['max_drawdown'].append(max_drawdown)
                    
                except Exception as e:
                    logger.error(f"Failed to analyze {symbol}: {e}")
                    continue
            
            # Calculate class averages
            if class_metrics['total_return']:
                performance_by_class[asset_class] = {
                    'avg_return': np.mean(class_metrics['total_return']),
                    'avg_volatility': np.mean(class_metrics['volatility']),
                    'avg_sharpe': np.mean(class_metrics['sharpe_ratio']),
                    'avg_max_drawdown': np.mean(class_metrics['max_drawdown']),
                    'count': len(class_metrics['total_return']),
                    'symbols': class_symbols
                }
        
        return performance_by_class

    def suggest_multi_asset_allocation(self, 
                                     risk_profile: str = "moderate", 
                                     investment_horizon: str = "medium",
                                     total_portfolio_value: float = 100000) -> Dict[AssetClass, float]:
        """Suggest asset allocation based on risk profile"""
        
        allocations = {
            "conservative": {
                AssetClass.STOCK: 0.30,
                AssetClass.BOND: 0.40,
                AssetClass.REIT: 0.10,
                AssetClass.COMMODITY: 0.05,
                AssetClass.CRYPTO: 0.05,
                AssetClass.ETF: 0.10
            },
            "moderate": {
                AssetClass.STOCK: 0.45,
                AssetClass.BOND: 0.25,
                AssetClass.REIT: 0.10,
                AssetClass.COMMODITY: 0.10,
                AssetClass.CRYPTO: 0.10,
                AssetClass.ETF: 0.00
            },
            "aggressive": {
                AssetClass.STOCK: 0.60,
                AssetClass.BOND: 0.10,
                AssetClass.REIT: 0.10,
                AssetClass.COMMODITY: 0.05,
                AssetClass.CRYPTO: 0.15,
                AssetClass.ETF: 0.00
            }
        }
        
        # Adjust for investment horizon
        base_allocation = allocations.get(risk_profile, allocations["moderate"])
        
        if investment_horizon == "short":  # < 3 years
            # Increase bonds, reduce stocks and crypto
            base_allocation[AssetClass.BOND] += 0.10
            base_allocation[AssetClass.STOCK] -= 0.05
            base_allocation[AssetClass.CRYPTO] -= 0.05
            
        elif investment_horizon == "long":  # > 10 years
            # Increase stocks and crypto, reduce bonds
            base_allocation[AssetClass.STOCK] += 0.10
            base_allocation[AssetClass.CRYPTO] += 0.05
            base_allocation[AssetClass.BOND] -= 0.15
        
        # Normalize to 100%
        total = sum(base_allocation.values())
        normalized_allocation = {k: v/total for k, v in base_allocation.items() if v > 0}
        
        return normalized_allocation

    def _period_to_days(self, period: str) -> int:
        """Convert period string to days"""
        period_map = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "10y": 3650
        }
        return period_map.get(period, 365)

    def _cache_price_data(self, symbol: str, df: pd.DataFrame) -> None:
        """Cache price data to disk"""
        try:
            cache_file = self.cache_dir / f"{symbol}_prices.json"
            
            # Convert to JSON-serializable format
            data = {
                'timestamp': df.index.strftime('%Y-%m-%d').tolist(),
                'close': df['close'].tolist(),
                'volume': df.get('volume', []).tolist() if 'volume' in df.columns else [],
                'cached_at': datetime.now().isoformat()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f)
                
        except Exception as e:
            logger.error(f"Failed to cache price data for {symbol}: {e}")

    def get_cached_price_data(self, symbol: str, max_age_hours: int = 24) -> Optional[pd.DataFrame]:
        """Get cached price data if available and fresh"""
        try:
            cache_file = self.cache_dir / f"{symbol}_prices.json"
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check cache age
            cached_at = datetime.fromisoformat(data['cached_at'])
            if (datetime.now() - cached_at).total_seconds() > max_age_hours * 3600:
                return None
            
            # Reconstruct DataFrame
            df = pd.DataFrame({
                'close': data['close'],
                'volume': data.get('volume', []),
                'symbol': symbol
            }, index=pd.to_datetime(data['timestamp']))
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load cached data for {symbol}: {e}")
            return None

# Global instance
multi_asset_manager = MultiAssetManager()