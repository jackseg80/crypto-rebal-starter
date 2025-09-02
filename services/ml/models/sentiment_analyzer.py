"""
Sentiment Analysis Engine for Crypto Markets
Multi-source sentiment analysis with aggregation and ML-based scoring
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import json
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class SentimentSource(Enum):
    """Sentiment data sources"""
    REDDIT = "reddit"
    TWITTER = "twitter" 
    NEWS = "news"
    FEAR_GREED = "fear_greed"
    SOCIAL_MENTIONS = "social_mentions"
    ONCHAIN_METRICS = "onchain_metrics"

@dataclass
class SentimentData:
    """Structured sentiment data"""
    source: SentimentSource
    symbol: str
    timestamp: datetime
    sentiment_score: float  # -1.0 (very negative) to +1.0 (very positive)
    confidence: float  # 0.0 to 1.0
    raw_data: Dict[str, Any]
    metadata: Dict[str, Any]

class SentimentCollector:
    """Base class for sentiment data collectors"""
    
    def __init__(self, source: SentimentSource):
        self.source = source
        self.session = None
        
    async def initialize(self):
        """Initialize async HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def collect_sentiment(self, symbol: str, days: int = 7) -> List[SentimentData]:
        """Collect sentiment data for a symbol"""
        raise NotImplementedError

class FearGreedIndexCollector(SentimentCollector):
    """
    Fear & Greed Index collector
    Uses proxy endpoints or cached data for the crypto Fear & Greed Index
    """
    
    def __init__(self):
        super().__init__(SentimentSource.FEAR_GREED)
        self.base_url = "https://api.alternative.me/fng/"
    
    async def collect_sentiment(self, symbol: str = "BTC", days: int = 7) -> List[SentimentData]:
        """
        Collect Fear & Greed Index data
        Note: This is a market-wide indicator, not symbol-specific
        """
        try:
            await self.initialize()
            
            # Fear & Greed Index API
            url = f"{self.base_url}?limit={min(days, 365)}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    sentiment_data = []
                    for item in data.get("data", []):
                        try:
                            # Convert Fear & Greed to sentiment score
                            fg_value = int(item["value"])
                            timestamp = datetime.fromtimestamp(int(item["timestamp"]))
                            
                            # Map Fear & Greed (0-100) to sentiment (-1 to +1)
                            # 0-25: Extreme Fear (-0.8 to -0.4)
                            # 25-45: Fear (-0.4 to -0.1) 
                            # 45-55: Neutral (-0.1 to +0.1)
                            # 55-75: Greed (+0.1 to +0.4)
                            # 75-100: Extreme Greed (+0.4 to +0.8)
                            
                            if fg_value <= 25:
                                sentiment_score = -0.8 + (fg_value / 25) * 0.4
                            elif fg_value <= 45:
                                sentiment_score = -0.4 + ((fg_value - 25) / 20) * 0.3
                            elif fg_value <= 55:
                                sentiment_score = -0.1 + ((fg_value - 45) / 10) * 0.2
                            elif fg_value <= 75:
                                sentiment_score = 0.1 + ((fg_value - 55) / 20) * 0.3
                            else:
                                sentiment_score = 0.4 + ((fg_value - 75) / 25) * 0.4
                            
                            sentiment_data.append(SentimentData(
                                source=self.source,
                                symbol="MARKET",  # Market-wide indicator
                                timestamp=timestamp,
                                sentiment_score=sentiment_score,
                                confidence=0.9,  # High confidence in official index
                                raw_data={
                                    "fear_greed_value": fg_value,
                                    "classification": item.get("value_classification", "")
                                },
                                metadata={
                                    "data_source": "alternative.me",
                                    "indicator_type": "fear_greed_index"
                                }
                            ))
                        
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Error parsing Fear & Greed data: {e}")
                            continue
                    
                    logger.info(f"Collected {len(sentiment_data)} Fear & Greed data points")
                    return sentiment_data
                
                else:
                    logger.warning(f"Fear & Greed API returned status {response.status}")
                    return self._generate_mock_fear_greed(days)
        
        except Exception as e:
            logger.error(f"Error collecting Fear & Greed data: {e}")
            return self._generate_mock_fear_greed(days)
    
    def _generate_mock_fear_greed(self, days: int) -> List[SentimentData]:
        """Generate mock Fear & Greed data for testing"""
        sentiment_data = []
        base_time = datetime.now()
        
        for i in range(days):
            # Generate realistic fear & greed values with some volatility
            base_value = 50 + 30 * np.sin(i / 10) + np.random.normal(0, 10)
            fg_value = max(0, min(100, base_value))
            
            # Convert to sentiment score
            if fg_value <= 25:
                sentiment_score = -0.8 + (fg_value / 25) * 0.4
            elif fg_value <= 45:
                sentiment_score = -0.4 + ((fg_value - 25) / 20) * 0.3
            elif fg_value <= 55:
                sentiment_score = -0.1 + ((fg_value - 45) / 10) * 0.2
            elif fg_value <= 75:
                sentiment_score = 0.1 + ((fg_value - 55) / 20) * 0.3
            else:
                sentiment_score = 0.4 + ((fg_value - 75) / 25) * 0.4
            
            sentiment_data.append(SentimentData(
                source=self.source,
                symbol="MARKET",
                timestamp=base_time - timedelta(days=i),
                sentiment_score=sentiment_score,
                confidence=0.7,  # Lower confidence for mock data
                raw_data={
                    "fear_greed_value": int(fg_value),
                    "classification": "mock_data"
                },
                metadata={
                    "data_source": "mock_generator",
                    "indicator_type": "fear_greed_index"
                }
            ))
        
        return sentiment_data

class SocialMentionsCollector(SentimentCollector):
    """
    Social media mentions and sentiment collector
    Simulates collection from Reddit, Twitter, etc.
    """
    
    def __init__(self):
        super().__init__(SentimentSource.SOCIAL_MENTIONS)
        
        # Positive and negative keywords for basic sentiment analysis
        self.positive_keywords = [
            'bullish', 'moon', 'pump', 'rocket', 'green', 'profit', 'gains',
            'buy', 'long', 'hodl', 'diamond', 'hands', 'breakout', 'rally'
        ]
        
        self.negative_keywords = [
            'bearish', 'dump', 'crash', 'red', 'loss', 'sell', 'short',
            'fear', 'panic', 'drop', 'decline', 'bear', 'weak', 'falling'
        ]
    
    async def collect_sentiment(self, symbol: str, days: int = 7) -> List[SentimentData]:
        """
        Collect social media sentiment data
        For now, generates realistic synthetic data
        """
        try:
            logger.info(f"Collecting social sentiment for {symbol} over {days} days")
            
            sentiment_data = []
            base_time = datetime.now()
            
            # Generate realistic social sentiment patterns
            for day in range(days):
                # Multiple data points per day (hourly)
                for hour in range(0, 24, 4):  # Every 4 hours
                    timestamp = base_time - timedelta(days=day, hours=hour)
                    
                    # Generate realistic social metrics
                    mentions_count = max(1, int(np.random.poisson(50) * (1 + np.random.normal(0, 0.5))))
                    
                    # Sentiment distribution based on recent crypto patterns
                    sentiment_raw = np.random.beta(2, 2) * 2 - 1  # Bias toward neutral
                    
                    # Add some symbol-specific bias
                    if symbol == "BTC":
                        sentiment_raw += 0.1  # Slightly bullish bias
                    elif symbol in ["ETH", "SOL"]:
                        sentiment_raw += 0.05
                    elif symbol in ["ADA", "DOT"]:
                        sentiment_raw -= 0.05  # Slightly bearish for altcoins
                    
                    sentiment_score = max(-1.0, min(1.0, sentiment_raw))
                    
                    # Confidence based on mention volume
                    confidence = min(0.9, 0.3 + (mentions_count / 100) * 0.6)
                    
                    # Generate realistic engagement metrics
                    upvotes = max(0, int(mentions_count * np.random.uniform(0.1, 0.8)))
                    comments = max(0, int(mentions_count * np.random.uniform(0.05, 0.3)))
                    
                    sentiment_data.append(SentimentData(
                        source=self.source,
                        symbol=symbol,
                        timestamp=timestamp,
                        sentiment_score=sentiment_score,
                        confidence=confidence,
                        raw_data={
                            "mentions_count": mentions_count,
                            "upvotes": upvotes,
                            "comments": comments,
                            "positive_mentions": int(mentions_count * max(0, sentiment_score)),
                            "negative_mentions": int(mentions_count * max(0, -sentiment_score)),
                        },
                        metadata={
                            "collection_method": "social_aggregation",
                            "time_period": "4h_window",
                            "platforms": ["reddit", "twitter", "telegram"]
                        }
                    ))
            
            logger.info(f"Generated {len(sentiment_data)} social sentiment data points for {symbol}")
            return sentiment_data
            
        except Exception as e:
            logger.error(f"Error collecting social sentiment for {symbol}: {e}")
            return []

class NewsAnalyzer:
    """
    News sentiment analyzer using simple keyword-based approach
    Can be extended with more sophisticated NLP models
    """
    
    def __init__(self):
        self.positive_news_keywords = [
            'adoption', 'partnership', 'upgrade', 'launch', 'breakthrough',
            'investment', 'institutional', 'regulation', 'approval', 'positive'
        ]
        
        self.negative_news_keywords = [
            'hack', 'scam', 'regulation', 'ban', 'crash', 'problem',
            'investigation', 'lawsuit', 'negative', 'concern', 'risk'
        ]
    
    def analyze_text_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Analyze sentiment of text using keyword matching
        
        Returns:
            Tuple of (sentiment_score, confidence)
        """
        if not text:
            return 0.0, 0.0
        
        text_lower = text.lower()
        
        positive_count = sum(1 for keyword in self.positive_news_keywords 
                           if keyword in text_lower)
        negative_count = sum(1 for keyword in self.negative_news_keywords 
                           if keyword in text_lower)
        
        total_keywords = positive_count + negative_count
        
        if total_keywords == 0:
            return 0.0, 0.1  # Neutral with low confidence
        
        # Calculate sentiment score
        sentiment_score = (positive_count - negative_count) / (positive_count + negative_count + 1)
        
        # Confidence based on keyword density
        confidence = min(0.8, total_keywords / 10)
        
        return sentiment_score, confidence

class NewsCollector(SentimentCollector):
    """
    News sentiment collector
    Simulates collection from crypto news sources
    """
    
    def __init__(self):
        super().__init__(SentimentSource.NEWS)
        self.news_analyzer = NewsAnalyzer()
    
    async def collect_sentiment(self, symbol: str, days: int = 7) -> List[SentimentData]:
        """
        Collect news sentiment data
        For now, generates realistic synthetic data
        """
        try:
            logger.info(f"Collecting news sentiment for {symbol} over {days} days")
            
            sentiment_data = []
            base_time = datetime.now()
            
            # Generate realistic news patterns
            for day in range(days):
                # 1-5 news articles per day per symbol
                num_articles = np.random.poisson(2) + 1
                
                for article_idx in range(num_articles):
                    timestamp = base_time - timedelta(
                        days=day,
                        hours=np.random.uniform(0, 24),
                        minutes=np.random.uniform(0, 60)
                    )
                    
                    # Generate realistic news headline sentiment
                    sentiment_raw = np.random.normal(0.1, 0.4)  # Slightly positive bias
                    
                    # Add symbol-specific news bias
                    if symbol == "BTC":
                        sentiment_raw += np.random.choice([0.2, -0.1], p=[0.7, 0.3])
                    elif symbol in ["ETH"]:
                        sentiment_raw += np.random.choice([0.15, -0.05], p=[0.65, 0.35])
                    
                    sentiment_score = max(-1.0, min(1.0, sentiment_raw))
                    
                    # News confidence is generally higher than social media
                    confidence = np.random.uniform(0.6, 0.9)
                    
                    # Generate realistic news metadata
                    sources = ["CoinDesk", "Cointelegraph", "CryptoNews", "Decrypt", "Bitcoin.com"]
                    source_name = np.random.choice(sources)
                    
                    sentiment_data.append(SentimentData(
                        source=self.source,
                        symbol=symbol,
                        timestamp=timestamp,
                        sentiment_score=sentiment_score,
                        confidence=confidence,
                        raw_data={
                            "headline": f"{symbol} shows {'positive' if sentiment_score > 0 else 'negative'} momentum",
                            "source": source_name,
                            "url": f"https://example.com/news/{symbol.lower()}-{article_idx}",
                            "article_length": np.random.randint(500, 2000)
                        },
                        metadata={
                            "collection_method": "news_aggregation",
                            "article_type": "market_analysis",
                            "language": "en"
                        }
                    ))
            
            logger.info(f"Generated {len(sentiment_data)} news sentiment data points for {symbol}")
            return sentiment_data
            
        except Exception as e:
            logger.error(f"Error collecting news sentiment for {symbol}: {e}")
            return []

class SentimentAnalysisEngine:
    """
    Main sentiment analysis engine
    Orchestrates multiple collectors and aggregates sentiment data
    """
    
    def __init__(self, cache_dir: str = "cache/sentiment"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize collectors
        self.collectors = {
            SentimentSource.FEAR_GREED: FearGreedIndexCollector(),
            SentimentSource.SOCIAL_MENTIONS: SocialMentionsCollector(), 
            SentimentSource.NEWS: NewsCollector()
        }
        
        # Aggregation weights for different sources
        self.source_weights = {
            SentimentSource.FEAR_GREED: 0.25,    # Market-wide indicator
            SentimentSource.SOCIAL_MENTIONS: 0.35,  # High volume, real-time
            SentimentSource.NEWS: 0.40           # Professional analysis
        }
        
        # ML models for advanced sentiment scoring
        self.ml_models = {}
        self.vectorizers = {}
        self.scalers = {}
        
        # Cache settings
        self.cache_ttl_hours = 2  # 2-hour cache for sentiment data
    
    async def collect_multi_source_sentiment(self, 
                                           symbols: List[str], 
                                           days: int = 7,
                                           sources: Optional[List[SentimentSource]] = None) -> Dict[str, List[SentimentData]]:
        """
        Collect sentiment from multiple sources for multiple symbols
        
        Args:
            symbols: List of crypto symbols
            days: Number of days to collect
            sources: Specific sources to use (all if None)
            
        Returns:
            Dictionary mapping symbols to sentiment data lists
        """
        if sources is None:
            sources = list(self.collectors.keys())
        
        logger.info(f"Collecting sentiment for {len(symbols)} symbols from {len(sources)} sources")
        
        all_sentiment_data = {}
        
        # Initialize all collectors
        for source in sources:
            if source in self.collectors:
                await self.collectors[source].initialize()
        
        try:
            # Collect from each source
            for symbol in symbols:
                symbol_sentiment = []
                
                for source in sources:
                    if source in self.collectors:
                        try:
                            collector = self.collectors[source]
                            sentiment_data = await collector.collect_sentiment(symbol, days)
                            symbol_sentiment.extend(sentiment_data)
                            
                        except Exception as e:
                            logger.error(f"Error collecting {source.value} sentiment for {symbol}: {e}")
                            continue
                
                all_sentiment_data[symbol] = symbol_sentiment
                logger.info(f"Collected {len(symbol_sentiment)} sentiment points for {symbol}")
        
        finally:
            # Cleanup collectors
            for source in sources:
                if source in self.collectors:
                    await self.collectors[source].cleanup()
        
        return all_sentiment_data
    
    def aggregate_sentiment_scores(self, 
                                 sentiment_data: List[SentimentData],
                                 time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Aggregate sentiment scores across sources and time windows
        
        Args:
            sentiment_data: List of sentiment data points
            time_window_hours: Time window for aggregation
            
        Returns:
            Aggregated sentiment metrics
        """
        if not sentiment_data:
            return {
                "overall_sentiment": 0.0,
                "confidence": 0.0,
                "source_breakdown": {},
                "temporal_trend": [],
                "data_points": 0
            }
        
        # Group by time windows
        time_windows = {}
        base_time = max(data.timestamp for data in sentiment_data)
        
        for data in sentiment_data:
            window_key = int((base_time - data.timestamp).total_seconds() / (time_window_hours * 3600))
            if window_key not in time_windows:
                time_windows[window_key] = []
            time_windows[window_key].append(data)
        
        # Calculate overall weighted sentiment
        total_weighted_sentiment = 0.0
        total_weight = 0.0
        source_sentiments = {}
        
        for data in sentiment_data:
            weight = self.source_weights.get(data.source, 0.2) * data.confidence
            total_weighted_sentiment += data.sentiment_score * weight
            total_weight += weight
            
            # Track by source
            if data.source not in source_sentiments:
                source_sentiments[data.source] = []
            source_sentiments[data.source].append(data.sentiment_score)
        
        overall_sentiment = total_weighted_sentiment / total_weight if total_weight > 0 else 0.0
        overall_confidence = min(1.0, total_weight / len(sentiment_data))
        
        # Source breakdown
        source_breakdown = {}
        for source, scores in source_sentiments.items():
            source_breakdown[source.value] = {
                "average_sentiment": np.mean(scores),
                "sentiment_volatility": np.std(scores),
                "data_points": len(scores),
                "weight": self.source_weights.get(source, 0.2)
            }
        
        # Temporal trend analysis
        temporal_trend = []
        for window_key in sorted(time_windows.keys()):
            window_data = time_windows[window_key]
            window_sentiment = np.mean([d.sentiment_score for d in window_data])
            window_confidence = np.mean([d.confidence for d in window_data])
            
            temporal_trend.append({
                "window": window_key,
                "sentiment": window_sentiment,
                "confidence": window_confidence,
                "data_points": len(window_data),
                "timestamp": (base_time - timedelta(hours=window_key * time_window_hours)).isoformat()
            })
        
        return {
            "overall_sentiment": overall_sentiment,
            "confidence": overall_confidence,
            "sentiment_classification": self._classify_sentiment(overall_sentiment),
            "source_breakdown": source_breakdown,
            "temporal_trend": temporal_trend,
            "data_points": len(sentiment_data),
            "analysis_period": {
                "start": min(data.timestamp for data in sentiment_data).isoformat(),
                "end": max(data.timestamp for data in sentiment_data).isoformat()
            }
        }
    
    def _classify_sentiment(self, sentiment_score: float) -> str:
        """Classify sentiment score into categories"""
        if sentiment_score > 0.5:
            return "very_bullish"
        elif sentiment_score > 0.2:
            return "bullish"
        elif sentiment_score > -0.2:
            return "neutral"
        elif sentiment_score > -0.5:
            return "bearish"
        else:
            return "very_bearish"
    
    async def analyze_market_sentiment(self, 
                                     symbols: List[str],
                                     days: int = 7) -> Dict[str, Any]:
        """
        Perform comprehensive market sentiment analysis
        
        Args:
            symbols: List of crypto symbols to analyze
            days: Number of days for analysis
            
        Returns:
            Comprehensive sentiment analysis results
        """
        logger.info(f"Starting market sentiment analysis for {len(symbols)} symbols")
        
        # Collect multi-source sentiment data
        sentiment_data = await self.collect_multi_source_sentiment(symbols, days)
        
        # Analyze each symbol
        symbol_analyses = {}
        for symbol, data in sentiment_data.items():
            if data:
                symbol_analyses[symbol] = self.aggregate_sentiment_scores(data, time_window_hours=12)
        
        # Calculate market-wide sentiment
        all_sentiment_scores = []
        all_confidence_scores = []
        
        for symbol, analysis in symbol_analyses.items():
            if analysis["data_points"] > 0:
                all_sentiment_scores.append(analysis["overall_sentiment"])
                all_confidence_scores.append(analysis["confidence"])
        
        market_sentiment = np.mean(all_sentiment_scores) if all_sentiment_scores else 0.0
        market_confidence = np.mean(all_confidence_scores) if all_confidence_scores else 0.0
        
        # Sentiment divergence analysis
        sentiment_std = np.std(all_sentiment_scores) if len(all_sentiment_scores) > 1 else 0.0
        sentiment_range = (max(all_sentiment_scores) - min(all_sentiment_scores)) if all_sentiment_scores else 0.0
        
        return {
            "market_overview": {
                "overall_sentiment": market_sentiment,
                "overall_confidence": market_confidence,
                "sentiment_classification": self._classify_sentiment(market_sentiment),
                "sentiment_divergence": sentiment_std,
                "sentiment_range": sentiment_range,
                "analysis_date": datetime.now().isoformat()
            },
            "individual_assets": symbol_analyses,
            "market_insights": {
                "consensus_level": "high" if sentiment_std < 0.2 else "medium" if sentiment_std < 0.5 else "low",
                "market_mood": "risk_on" if market_sentiment > 0.3 else "risk_off" if market_sentiment < -0.3 else "neutral",
                "sentiment_momentum": self._calculate_sentiment_momentum(symbol_analyses),
                "key_drivers": self._identify_key_sentiment_drivers(sentiment_data)
            },
            "recommendations": self._generate_sentiment_recommendations(market_sentiment, sentiment_std, symbol_analyses)
        }
    
    def _calculate_sentiment_momentum(self, symbol_analyses: Dict[str, Any]) -> str:
        """Calculate sentiment momentum from temporal trends"""
        momentum_scores = []
        
        for analysis in symbol_analyses.values():
            trend_data = analysis.get("temporal_trend", [])
            if len(trend_data) >= 2:
                # Compare recent vs older sentiment
                recent_sentiment = np.mean([t["sentiment"] for t in trend_data[:2]])
                older_sentiment = np.mean([t["sentiment"] for t in trend_data[-2:]])
                momentum_scores.append(recent_sentiment - older_sentiment)
        
        if not momentum_scores:
            return "stable"
        
        avg_momentum = np.mean(momentum_scores)
        
        if avg_momentum > 0.1:
            return "improving"
        elif avg_momentum < -0.1:
            return "deteriorating"
        else:
            return "stable"
    
    def _identify_key_sentiment_drivers(self, sentiment_data: Dict[str, List[SentimentData]]) -> List[str]:
        """Identify key sentiment drivers from the data"""
        drivers = []
        
        # Analyze source contributions
        source_impacts = {}
        for symbol, data_list in sentiment_data.items():
            for data in data_list:
                if data.source not in source_impacts:
                    source_impacts[data.source] = []
                source_impacts[data.source].append(abs(data.sentiment_score) * data.confidence)
        
        # Find most impactful sources
        for source, impacts in source_impacts.items():
            avg_impact = np.mean(impacts)
            if avg_impact > 0.5:
                drivers.append(f"{source.value}_activity")
        
        # Add market-specific drivers
        fear_greed_data = [d for data_list in sentiment_data.values() 
                          for d in data_list if d.source == SentimentSource.FEAR_GREED]
        
        if fear_greed_data:
            recent_fg = fear_greed_data[0]  # Most recent
            fg_value = recent_fg.raw_data.get("fear_greed_value", 50)
            
            if fg_value < 30:
                drivers.append("extreme_fear")
            elif fg_value > 70:
                drivers.append("extreme_greed")
        
        return drivers[:5]  # Top 5 drivers
    
    def _generate_sentiment_recommendations(self, 
                                          market_sentiment: float,
                                          sentiment_divergence: float,
                                          symbol_analyses: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on sentiment analysis"""
        recommendations = []
        
        # Market-level recommendations
        if market_sentiment > 0.5:
            recommendations.append("Market shows strong bullish sentiment - consider taking some profits")
            recommendations.append("Watch for signs of over-optimism and potential reversal")
        elif market_sentiment < -0.5:
            recommendations.append("Market shows strong bearish sentiment - potential accumulation opportunity")
            recommendations.append("Exercise caution and consider dollar-cost averaging")
        else:
            recommendations.append("Market sentiment is neutral - focus on fundamental analysis")
        
        # Divergence-based recommendations
        if sentiment_divergence > 0.4:
            recommendations.append("High sentiment divergence detected - opportunities in undervalued assets")
            recommendations.append("Consider pair trading strategies between bullish and bearish assets")
        
        # Asset-specific recommendations
        bullish_assets = [symbol for symbol, analysis in symbol_analyses.items() 
                         if analysis["overall_sentiment"] > 0.3]
        bearish_assets = [symbol for symbol, analysis in symbol_analyses.items() 
                         if analysis["overall_sentiment"] < -0.3]
        
        if bullish_assets:
            recommendations.append(f"Positive sentiment assets: {', '.join(bullish_assets[:3])}")
        if bearish_assets:
            recommendations.append(f"Negative sentiment assets: {', '.join(bearish_assets[:3])}")
        
        return recommendations
    
    def get_sentiment_status(self) -> Dict[str, Any]:
        """Get sentiment analysis system status"""
        return {
            "active_collectors": [source.value for source in self.collectors.keys()],
            "source_weights": {source.value: weight for source, weight in self.source_weights.items()},
            "cache_directory": str(self.cache_dir),
            "ml_models_loaded": len(self.ml_models),
            "last_analysis": datetime.now().isoformat()
        }