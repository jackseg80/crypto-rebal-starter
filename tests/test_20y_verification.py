"""
Test script to verify ML regime detection is using 20 years (7300 days).
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 80)
print("VERIFICATION: ML Regime Detection - 20 Years Training")
print("=" * 80)

# Test 1: Model Info Endpoint
print("\n1. Testing /api/ml/bourse/model-info endpoint...")
try:
    response = requests.get(f"{BASE_URL}/api/ml/bourse/model-info?model_type=regime")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Model exists: {data.get('exists')}")
        print(f"   📅 Last trained: {data.get('last_trained')}")
        print(f"   ⏱️  Age: {data.get('age_hours', 0):.2f} hours ({data.get('age_days', 0):.2f} days)")
        print(f"   🔄 Needs retrain: {data.get('needs_retrain')}")
        print(f"   📊 Training interval: {data.get('training_interval_days')} days")
    else:
        print(f"   ❌ Error: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Regime Detection Endpoint (check response metadata)
print("\n2. Testing /api/ml/bourse/regime endpoint...")
try:
    response = requests.get(f"{BASE_URL}/api/ml/bourse/regime?benchmark=SPY&lookback_days=7300")
    if response.status_code == 200:
        data = response.json()

        # Check metadata for lookback_days
        metadata = data.get('metadata', {})
        training_meta = data.get('training_metadata', {})

        print(f"   📈 Current regime: {data.get('current_regime')}")
        print(f"   🎯 Confidence: {data.get('confidence', 0):.1%}")

        # Check for training samples (should be 1800-2400 for 20 years)
        training_samples = training_meta.get('training_samples', 0)
        if training_samples > 0:
            print(f"   🔢 Training samples: {training_samples}")
            if training_samples >= 1800:
                print(f"      ✅ CONFIRMED: Using 20 years data (1800-2400 samples expected)")
            elif training_samples >= 450:
                print(f"      ⚠️  WARNING: Seems like 5 years data (450-600 samples)")
            else:
                print(f"      ⚠️  WARNING: Less than expected samples")

        # Check class distribution
        class_dist = training_meta.get('class_distribution', [])
        if class_dist:
            print(f"   📊 Class distribution: {class_dist}")
            total = sum(class_dist)
            if total > 0:
                bear_pct = (class_dist[0] / total * 100) if len(class_dist) > 0 else 0
                print(f"      Bear Market: {bear_pct:.1f}% of samples")
                if bear_pct >= 20:
                    print(f"      ✅ CONFIRMED: Balanced distribution (20+ years expected)")
                else:
                    print(f"      ⚠️  WARNING: Low Bear % (may be < 20 years)")

        # Check lookback_days in metadata
        lookback = metadata.get('lookback_days') or training_meta.get('lookback_days')
        if lookback:
            print(f"   🕐 Lookback days: {lookback}")
            if lookback >= 7000:
                print(f"      ✅ CONFIRMED: Using 20 years (7300 days)")
            elif lookback >= 1800:
                print(f"      ⚠️  WARNING: Using 5 years (1825 days)")
            else:
                print(f"      ⚠️  WARNING: Using < 5 years ({lookback} days)")

        # Full response for debugging
        print(f"\n   📄 Full metadata:")
        print(f"      {json.dumps(metadata, indent=6)}")
        if training_meta:
            print(f"   📄 Full training metadata:")
            print(f"      {json.dumps(training_meta, indent=6)}")
    else:
        print(f"   ❌ Error: {response.status_code}")
        print(f"   {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Check logs file for training evidence
print("\n3. Checking logs for training evidence...")
try:
    with open("logs/app.log", "r", encoding="utf-8") as f:
        lines = f.readlines()[-200:]  # Last 200 lines

        training_lines = [l for l in lines if "Training regime" in l or "7300" in l or "20 years" in l]

        if training_lines:
            print(f"   ✅ Found {len(training_lines)} relevant log entries:")
            for line in training_lines[-5:]:  # Last 5
                print(f"      {line.strip()}")
        else:
            print(f"   ℹ️  No recent training logs (model may be cached)")
except Exception as e:
    print(f"   ⚠️  Could not read logs: {e}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("✅ If you see 'Training samples: 1800-2400' → Using 20 years")
print("✅ If you see 'Lookback days: 7300' → Using 20 years")
print("✅ If you see 'Bear Market: 20-30%' → Balanced distribution (20 years)")
print("⚠️  If you see 'Training samples: 450-600' → Still using 5 years")
print("=" * 80)
