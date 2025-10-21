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
    lookback_days: int = Query(365, ge=30, le=3650, description="Timeline period (days)")
):
    """
    Get historical Bitcoin regime timeline for chart visualization.

    Applies regime detection to each day in the period to build timeline.
    Includes price data and event annotations.

    Args:
        symbol: Crypto symbol (default: BTC)
        lookback_days: Timeline length (30 to 3650 days)

    Returns:
        dates: Array of ISO dates
        prices: Array of close prices
        regimes: Array of regime names
        regime_ids: Array of regime IDs (0-3)
        events: Array of annotated events
    """
    try:
        logger.info(f"GET /api/ml/crypto/regime-history - symbol={symbol}, lookback_days={lookback_days}")

        # Check cache first (huge performance boost)
        cache_key = f"{symbol}_{lookback_days}"
        now = datetime.now().timestamp()

        if cache_key in _regime_history_cache:
            cached_entry = _regime_history_cache[cache_key]
            age = now - cached_entry['timestamp']

            if age < _CACHE_TTL:
                logger.info(f"Cache HIT for {cache_key} (age: {age:.0f}s, TTL: {_CACHE_TTL}s)")
                return success_response(cached_entry['data'])
            else:
                logger.info(f"Cache EXPIRED for {cache_key} (age: {age:.0f}s > TTL: {_CACHE_TTL}s)")
                del _regime_history_cache[cache_key]

        logger.info(f"Cache MISS for {cache_key}, computing regime timeline...")

        # Get historical data from cache
        history = price_history.get_cached_history(symbol, days=lookback_days)

        if history is None or len(history) == 0:
            return error_response(f"No historical data available for {symbol}", code=404)

        # Convert to DataFrame (timestamps are in seconds)
        data = pd.DataFrame(history, columns=['timestamp', 'close'])
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='s')  # Seconds, not ms
        data.set_index('timestamp', inplace=True)
        data['volume'] = 1.0  # Constant volume

        logger.info(f"Loaded {len(data)} days of {symbol} data for regime timeline")

        # Create detector
        detector = BTCRegimeDetector()

        # OPTIMIZATION V2: Calculate features ONCE for entire series
        # Instead of 365 calls to prepare_regime_features (very slow),
        # we calculate all features once and use sliding window on results
        logger.info(f"Calculating features once for {len(data)} days (optimized)")

        # Calculate all features at once
        all_features = await detector.prepare_regime_features(
            symbol=symbol,
            lookback_days=lookback_days
        )

        logger.info(f"Features calculated: {len(all_features)} rows, {len(all_features.columns)} columns")

        # Train HMM once on full dataset
        await detector.train_hmm(symbol=symbol, lookback_days=lookback_days)

        # Apply regime detection to each day using PRE-CALCULATED features
        regimes = []
        regime_ids = []

        # Use expanding window on pre-calculated features
        for i in range(len(data)):
            try:
                # Skip if window too small (need at least 60 days for features)
                if i < 60:
                    regimes.append('Insufficient Data')
                    regime_ids.append(-1)
                    continue

                # Get features up to current day (just slicing, no recalculation!)
                window_features = all_features.iloc[:i+1]

                # Get last row for rule-based detection
                latest_features = window_features.iloc[[-1]]  # Keep as DataFrame

                # Get rule-based detection (fast, uses latest features only)
                rule_result = detector._detect_regime_rule_based(latest_features)

                if rule_result and rule_result['confidence'] >= 0.85:
                    # High confidence rule → use it
                    regimes.append(rule_result['regime_name'])
                    regime_ids.append(rule_result['regime_id'])
                else:
                    # Use HMM fallback (already trained)
                    features_scaled = detector.scaler.transform(window_features[detector.feature_columns])
                    regime_sequence = detector.hmm_model.predict(features_scaled)
                    regime_id = int(regime_sequence[-1])
                    regimes.append(detector.regime_names[regime_id])
                    regime_ids.append(regime_id)

            except Exception as e:
                logger.warning(f"Failed to predict regime for day {i}: {e}")
                regimes.append('Unknown')
                regime_ids.append(-1)

        # Get events in this period
        events = get_btc_events(data.index[0], data.index[-1])

        # Format response
        response_data = {
            'dates': data.index.strftime('%Y-%m-%d').tolist(),
            'prices': data['close'].tolist(),
            'regimes': regimes,
            'regime_ids': regime_ids,
            'events': events,
            'regime_id_mapping': {
                str(i): detector.regime_names[i]
                for i in range(detector.num_regimes)
            },
            'symbol': symbol,
            'period_days': len(data),
            'start_date': data.index[0].strftime('%Y-%m-%d'),
            'end_date': data.index[-1].strftime('%Y-%m-%d')
        }

        # Calculate regime distribution for logging
        regime_counts = {}
        for regime in regimes:
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        logger.info(f"Regime timeline built: {len(regimes)} days, distribution={regime_counts}")

        # Store in cache for future requests (huge performance boost)
        _regime_history_cache[cache_key] = {
            'data': response_data,
            'timestamp': now
        }
        logger.info(f"Cached regime timeline for {cache_key} (TTL: {_CACHE_TTL}s)")

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
