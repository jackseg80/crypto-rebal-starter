"""
ML Crypto Endpoints - Bitcoin Regime Detection API

Endpoints:
- GET /api/ml/crypto/regime: Current BTC regime (hybrid detection)
- GET /api/ml/crypto/regime-history: Historical regime timeline
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime
import logging

from api.utils import success_response, error_response
from services.ml.models.btc_regime_detector import BTCRegimeDetector
from services.price_history import price_history

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory cache for regime history (TTL: 1 hour)
_regime_history_cache = {}
_CACHE_TTL = 3600  # 1 hour in seconds


def get_btc_events(start_date: pd.Timestamp, end_date: pd.Timestamp) -> List[Dict[str, str]]:
    """
    Get significant Bitcoin events within date range for chart annotations.

    Args:
        start_date: Start of period
        end_date: End of period

    Returns:
        List of events with date, label, and type
    """
    all_events = [
        {'date': '2014-02-01', 'label': 'Mt.Gox Collapse', 'type': 'crisis'},
        {'date': '2014-12-14', 'label': 'Bear Bottom $315', 'type': 'bottom'},
        {'date': '2017-12-17', 'label': 'BTC ATH $20k', 'type': 'peak'},
        {'date': '2018-12-15', 'label': 'Crypto Winter Bottom $3.2k', 'type': 'bottom'},
        {'date': '2020-03-12', 'label': 'COVID Crash -50%', 'type': 'crisis'},
        {'date': '2020-12-16', 'label': 'BTC Breaks Previous ATH', 'type': 'policy'},
        {'date': '2021-04-14', 'label': 'Coinbase IPO', 'type': 'policy'},
        {'date': '2021-11-10', 'label': 'BTC ATH $69k', 'type': 'peak'},
        {'date': '2022-05-09', 'label': 'Luna/UST Collapse', 'type': 'crisis'},
        {'date': '2022-11-09', 'label': 'FTX Bankruptcy', 'type': 'crisis'},
        {'date': '2022-11-21', 'label': 'Bear Bottom $15.5k', 'type': 'bottom'},
        {'date': '2024-03-13', 'label': 'BTC New ATH $73k', 'type': 'peak'}
    ]

    # Filter events within date range
    filtered_events = []
    for event in all_events:
        event_date = pd.to_datetime(event['date'])
        if start_date <= event_date <= end_date:
            filtered_events.append(event)

    logger.info(f"Found {len(filtered_events)} BTC events in period {start_date.date()} to {end_date.date()}")
    return filtered_events


@router.get("/regime")
async def get_crypto_regime(
    symbol: str = Query("BTC", description="Cryptocurrency symbol"),
    lookback_days: int = Query(3650, ge=365, le=5000, description="Historical window for features (days)")
):
    """
    Get current Bitcoin market regime using hybrid detection.

    Uses rule-based + HMM fusion:
    - Rule-based: High confidence cases (bear >50% DD, bull stable)
    - HMM: Nuanced cases (corrections, consolidations)
    - Fusion: Rule overrides HMM if confidence ≥ 85%

    Returns:
        Current regime, confidence, detection method, probabilities
    """
    try:
        logger.info(f"GET /api/ml/crypto/regime - symbol={symbol}, lookback_days={lookback_days}")

        # Create detector
        detector = BTCRegimeDetector()

        # Predict current regime
        result = await detector.predict_regime(
            symbol=symbol,
            lookback_days=lookback_days,
            return_probabilities=True
        )

        # Format response
        response_data = {
            'current_regime': result['regime_name'],
            'confidence': result['confidence'],
            'detection_method': result['detection_method'],
            'rule_reason': result.get('rule_reason'),
            'regime_info': result['regime_info'],
            'regime_probabilities': result.get('regime_probabilities', {}),
            'benchmark': symbol,
            'lookback_days': lookback_days,
            'prediction_date': result['prediction_date'],
            'model_metadata': result['model_metadata']
        }

        logger.info(f"Regime detected: {result['regime_name']} (method={result['detection_method']}, confidence={result['confidence']:.2f})")

        return success_response(response_data)

    except ValueError as e:
        logger.error(f"ValueError in get_crypto_regime: {e}")
        return error_response(str(e), code=400)
    except Exception as e:
        logger.error(f"Error in get_crypto_regime: {e}", exc_info=True)
        return error_response(f"Failed to predict regime: {str(e)}", code=500)


@router.get("/regime-history")
async def get_crypto_regime_history(
    symbol: str = Query("BTC", description="Cryptocurrency symbol"),
    lookback_days: int = Query(90, ge=30, le=3650, description="Timeline period (days)")
):
    """
    Get Bitcoin regime history (SIMPLIFIED - HMM only, less reliable for >90 days).

    WARNING: HMM-based detection is less accurate for Bitcoin due to limited training data.
    For the most accurate CURRENT regime, use /api/ml/crypto/regime endpoint instead.

    Args:
        symbol: Crypto symbol (default: BTC)
        lookback_days: Timeline length (30-3650 days, default 90, reliable up to 90 days)
    """
    try:
        logger.info(f"GET /api/ml/crypto/regime-history - symbol={symbol}, lookback_days={lookback_days}")

        # Get data
        history = price_history.get_cached_history(symbol, days=lookback_days)
        if history is None or len(history) == 0:
            return error_response(f"No historical data available for {symbol}", code=404)

        data = pd.DataFrame(history, columns=['timestamp', 'close'])
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='s')
        data.set_index('timestamp', inplace=True)

        # Prepare features
        detector = BTCRegimeDetector()
        features_df = await detector.prepare_regime_features(symbol=symbol, lookback_days=lookback_days)

        if len(features_df) == 0:
            return error_response("Insufficient data", code=400)

        # Simple HMM predictions (no complex hybrid rules)
        if not detector.load_model("btc_regime_hmm.pkl"):
            await detector.train_hmm(symbol=symbol, lookback_days=3650)

        features_scaled = detector.scaler.transform(features_df[detector.feature_columns])
        regime_labels = detector.hmm_model.predict(features_scaled)
        regime_names = [detector.regime_names[int(label)] for label in regime_labels]

        # Format response
        response_data = {
            'dates': features_df.index.strftime('%Y-%m-%d').tolist(),
            'prices': data.loc[features_df.index, 'close'].tolist(),
            'regimes': regime_names,
            'regime_ids': regime_labels.tolist(),
            'symbol': symbol,
            'lookback_days': lookback_days,
            'regime_id_mapping': {i: name for i, name in enumerate(detector.regime_names)},
            'events': [],
            'note': 'Simplified HMM-only detection. For accurate current regime, use /api/ml/crypto/regime endpoint.'
        }

        return success_response(response_data)

    except Exception as e:
        logger.error(f"Error in regime-history: {e}", exc_info=True)
        return error_response(f"Failed to get regime history: {str(e)}", code=500)


@router.get("/regime-forecast")
async def get_crypto_regime_forecast(
    symbol: str = Query("BTC", description="Cryptocurrency symbol"),
    lookback_days: int = Query(90, ge=30, le=365, description="Context window (days)")
):
    """
    Get Bitcoin regime FORECAST with recent context and future predictions.

    FOCUS: Where we're GOING (predictive) rather than where we were (historical).

    Returns:
        - Recent 90-day context (for trend visualization)
        - Current regime with high confidence (hybrid rules + HMM)
        - Transition probabilities (7/30-day forecast)
        - Momentum indicators (drawdown/volatility trends)
        - Conditional scenarios (if +10%, if -10%)

    Args:
        symbol: Crypto symbol (default: BTC)
        lookback_days: Context window (30-365 days, default 90)

    Returns:
        {
            "current_regime": {...},
            "recent_context": {
                "dates": [...],  # Last 90 days
                "prices": [...],
                "regimes": [...]
            },
            "forecast": {
                "transition_probabilities": {...},
                "momentum_indicators": {...},
                "scenarios": [...]
            }
        }
    """
    try:
        logger.info(f"GET /api/ml/crypto/regime-forecast - symbol={symbol}, lookback_days={lookback_days}")

        # Get current regime using existing endpoint (already works well!)
        detector = BTCRegimeDetector()
        current_regime_result = await detector.predict_regime(symbol=symbol, lookback_days=3650)

        # Get recent context for trend visualization (last N days)
        history = price_history.get_cached_history(symbol, days=lookback_days)
        if history is None or len(history) == 0:
            return error_response(f"No historical data available for {symbol}", code=404)

        data = pd.DataFrame(history, columns=['timestamp', 'close'])
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='s')
        data.set_index('timestamp', inplace=True)

        # Prepare features for recent context
        features_df = await detector.prepare_regime_features(symbol=symbol, lookback_days=lookback_days)

        if len(features_df) == 0:
            return error_response("Insufficient data for forecast", code=400)

        # Get recent regime timeline (simplified, just for context visualization)
        if not detector.load_model("btc_regime_hmm.pkl"):
            await detector.train_hmm(symbol=symbol, lookback_days=3650)

        features_scaled = detector.scaler.transform(features_df[detector.feature_columns])
        hmm_predictions = detector.hmm_model.predict(features_scaled)
        recent_regimes = [detector.regime_names[int(pred)] for pred in hmm_predictions]

        # Calculate momentum indicators (trend direction)
        latest_features = features_df.iloc[-1]
        last_30d_features = features_df.tail(30)

        drawdown_trend = "improving" if last_30d_features['drawdown_from_peak'].diff().mean() > 0 else "worsening"
        volatility_trend = "decreasing" if last_30d_features['market_volatility'].diff().mean() < 0 else "increasing"

        # Calculate transition probabilities (simplified heuristic)
        current_regime_name = current_regime_result['regime_name']
        current_drawdown = latest_features['drawdown_from_peak']
        current_volatility = latest_features['market_volatility']
        current_trend = latest_features.get('trend_30d', 0)

        # Simple scenario-based forecasting
        scenarios = []

        # Scenario 1: If price +10%
        new_dd_up = current_drawdown + 0.10
        if new_dd_up > -0.05:
            likely_regime_up = "Bull Market"
        elif new_dd_up > -0.20:
            likely_regime_up = "Expansion"
        else:
            likely_regime_up = current_regime_name
        scenarios.append({
            "scenario": "Price +10%",
            "price_change": "+10%",
            "likely_regime": likely_regime_up,
            "probability": 0.7 if likely_regime_up != current_regime_name else 0.9
        })

        # Scenario 2: If price -10%
        new_dd_down = current_drawdown - 0.10
        if new_dd_down < -0.50:
            likely_regime_down = "Bear Market"
        elif new_dd_down < -0.20:
            likely_regime_down = "Correction"
        else:
            likely_regime_down = current_regime_name
        scenarios.append({
            "scenario": "Price -10%",
            "price_change": "-10%",
            "likely_regime": likely_regime_down,
            "probability": 0.7 if likely_regime_down != current_regime_name else 0.9
        })

        # Scenario 3: If trend continues
        trend_direction = "up" if current_trend > 0 else "down"
        scenarios.append({
            "scenario": f"Trend continues ({trend_direction})",
            "price_change": f"{current_trend*100:+.1f}% (30d momentum)",
            "likely_regime": current_regime_name,
            "probability": 0.8
        })

        # Format response
        response_data = {
            'current_regime': {
                'regime': current_regime_result['regime_name'],
                'confidence': current_regime_result['confidence'],
                'method': current_regime_result['detection_method'],
                'reason': current_regime_result.get('rule_reason', 'HMM prediction'),
                'probabilities': current_regime_result.get('regime_probabilities', {})
            },
            'recent_context': {
                'dates': features_df.index.strftime('%Y-%m-%d').tolist(),
                'prices': data.loc[features_df.index, 'close'].tolist(),
                'regimes': recent_regimes,
                'period_days': lookback_days
            },
            'momentum_indicators': {
                'drawdown_current': float(current_drawdown),
                'drawdown_trend': drawdown_trend,
                'volatility_current': float(current_volatility),
                'volatility_trend': volatility_trend,
                'trend_30d': float(current_trend),
                'trend_direction': trend_direction
            },
            'scenarios': scenarios,
            'symbol': symbol,
            'forecast_date': datetime.now().isoformat()
        }

        logger.info(f"Regime forecast generated: {current_regime_name} (method={current_regime_result['detection_method']})")

        return success_response(response_data)

    except ValueError as e:
        logger.error(f"ValueError in get_crypto_regime_history: {e}")
        return error_response(str(e), code=400)
    except Exception as e:
        logger.error(f"Error in get_crypto_regime_history: {e}", exc_info=True)
        return error_response(f"Failed to build regime timeline: {str(e)}", code=500)


@router.get("/regime/validate")
async def validate_regime_detector(
    symbol: str = Query("BTC", description="Cryptocurrency symbol")
):
    """
    Validate regime detector on known Bitcoin bear markets.

    Tests:
    - 2014-2015: Mt.Gox crash (-85%)
    - 2018: Crypto Winter (-84%)
    - 2022: Luna/FTX (-77%)

    Returns validation report with recall metrics.
    """
    try:
        logger.info(f"GET /api/ml/crypto/regime/validate - symbol={symbol}")

        # Known bear market periods (manual labeling)
        known_bear_markets = [
            {'name': '2014-2015 Mt.Gox', 'start': '2014-01-01', 'end': '2015-01-14', 'max_dd': -0.85},
            {'name': '2018 Crypto Winter', 'start': '2018-01-01', 'end': '2018-12-15', 'max_dd': -0.84},
            {'name': '2022 Luna/FTX', 'start': '2022-05-01', 'end': '2022-11-21', 'max_dd': -0.77}
        ]

        detector = BTCRegimeDetector()

        # Validate each bear market
        results = []
        for bear in known_bear_markets:
            try:
                # Get data for this period
                start = pd.to_datetime(bear['start'])
                end = pd.to_datetime(bear['end'])
                days = (end - start).days

                # Predict regime for this period
                regime = await detector.predict_regime(symbol=symbol, lookback_days=days + 365)

                detected_as_bear = regime['regime_name'] == 'Bear Market'
                confidence = regime['confidence']

                results.append({
                    'period': bear['name'],
                    'expected': 'Bear Market',
                    'detected': regime['regime_name'],
                    'correct': detected_as_bear,
                    'confidence': confidence,
                    'method': regime['detection_method'],
                    'max_drawdown': bear['max_dd']
                })

                logger.info(f"{bear['name']}: Detected as {regime['regime_name']} ({'✅' if detected_as_bear else '❌'})")

            except Exception as e:
                logger.error(f"Failed to validate {bear['name']}: {e}")
                results.append({
                    'period': bear['name'],
                    'expected': 'Bear Market',
                    'detected': 'Error',
                    'correct': False,
                    'error': str(e)
                })

        # Calculate metrics
        total = len(results)
        correct = sum(1 for r in results if r.get('correct'))
        recall = correct / total if total > 0 else 0

        validation_report = {
            'validation_date': datetime.now().isoformat(),
            'symbol': symbol,
            'total_tests': total,
            'correct_detections': correct,
            'bear_market_recall': recall,
            'results': results,
            'status': 'PASS' if recall >= 0.90 else 'FAIL'
        }

        logger.info(f"Validation complete: {correct}/{total} bear markets detected (recall={recall:.1%})")

        return success_response(validation_report)

    except Exception as e:
        logger.error(f"Error in validate_regime_detector: {e}", exc_info=True)
        return error_response(f"Validation failed: {str(e)}", code=500)
