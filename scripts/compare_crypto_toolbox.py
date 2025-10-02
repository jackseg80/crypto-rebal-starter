#!/usr/bin/env python3
"""
Compare Crypto-Toolbox outputs between Flask and FastAPI implementations.

Usage:
    python scripts/compare_crypto_toolbox.py flask_output.json fastapi_output.json
"""

import json
import sys
from typing import Dict, List, Any


def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {filepath}: {e}")
        sys.exit(1)


def compare_counts(flask_data: Dict, fastapi_data: Dict) -> bool:
    """Compare total_count and critical_count"""
    flask_total = flask_data.get('total_count', 0)
    fastapi_total = fastapi_data.get('total_count', 0)
    flask_critical = flask_data.get('critical_count', 0)
    fastapi_critical = fastapi_data.get('critical_count', 0)

    print(f"\n{'='*60}")
    print("COUNTS COMPARISON")
    print(f"{'='*60}")
    print(f"Total count   - Flask: {flask_total:2d} | FastAPI: {fastapi_total:2d} | Match: {'✅' if flask_total == fastapi_total else '❌'}")
    print(f"Critical count - Flask: {flask_critical:2d} | FastAPI: {fastapi_critical:2d} | Match: {'✅' if flask_critical == fastapi_critical else '❌'}")

    return flask_total == fastapi_total and flask_critical == fastapi_critical


def compare_indicator_names(flask_data: Dict, fastapi_data: Dict) -> bool:
    """Compare indicator names (unordered)"""
    flask_names = {ind['name'] for ind in flask_data.get('indicators', [])}
    fastapi_names = {ind['name'] for ind in fastapi_data.get('indicators', [])}

    only_flask = flask_names - fastapi_names
    only_fastapi = fastapi_names - flask_names

    print(f"\n{'='*60}")
    print("INDICATOR NAMES COMPARISON")
    print(f"{'='*60}")
    print(f"Flask unique: {len(flask_names)} | FastAPI unique: {len(fastapi_names)}")

    if only_flask:
        print(f"\n❌ Only in Flask ({len(only_flask)}):")
        for name in sorted(only_flask):
            print(f"   - {name}")

    if only_fastapi:
        print(f"\n❌ Only in FastAPI ({len(only_fastapi)}):")
        for name in sorted(only_fastapi):
            print(f"   - {name}")

    if not only_flask and not only_fastapi:
        print("✅ All indicator names match")
        return True

    return False


def compare_values(flask_data: Dict, fastapi_data: Dict, tolerance: float = 0.01) -> bool:
    """Compare numeric values and critical zones"""
    flask_inds = {ind['name']: ind for ind in flask_data.get('indicators', [])}
    fastapi_inds = {ind['name']: ind for ind in fastapi_data.get('indicators', [])}

    common_names = set(flask_inds.keys()) & set(fastapi_inds.keys())

    mismatches = []

    for name in sorted(common_names):
        flask_ind = flask_inds[name]
        fastapi_ind = fastapi_inds[name]

        flask_val = flask_ind.get('value_numeric', 0)
        fastapi_val = fastapi_ind.get('value_numeric', 0)
        flask_crit = flask_ind.get('in_critical_zone', False)
        fastapi_crit = fastapi_ind.get('in_critical_zone', False)

        val_diff = abs(flask_val - fastapi_val)
        val_match = val_diff <= tolerance
        crit_match = flask_crit == fastapi_crit

        if not val_match or not crit_match:
            mismatches.append({
                'name': name,
                'flask_value': flask_val,
                'fastapi_value': fastapi_val,
                'value_diff': val_diff,
                'value_match': val_match,
                'flask_critical': flask_crit,
                'fastapi_critical': fastapi_crit,
                'critical_match': crit_match
            })

    print(f"\n{'='*60}")
    print("VALUES & CRITICAL ZONES COMPARISON")
    print(f"{'='*60}")
    print(f"Common indicators: {len(common_names)}")

    if mismatches:
        print(f"\n❌ Mismatches found ({len(mismatches)}):")
        for m in mismatches:
            print(f"\n   {m['name']}:")
            if not m['value_match']:
                print(f"      Value: Flask {m['flask_value']:.2f} | FastAPI {m['fastapi_value']:.2f} (diff: {m['value_diff']:.2f})")
            if not m['critical_match']:
                print(f"      Critical: Flask {m['flask_critical']} | FastAPI {m['fastapi_critical']}")
        return False
    else:
        print(f"✅ All values match (tolerance: ±{tolerance})")
        print("✅ All critical zones match")
        return True


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/compare_crypto_toolbox.py flask_output.json fastapi_output.json")
        sys.exit(1)

    flask_file = sys.argv[1]
    fastapi_file = sys.argv[2]

    print(f"\n{'='*60}")
    print("CRYPTO-TOOLBOX A/B COMPARISON")
    print(f"{'='*60}")
    print(f"Flask file:   {flask_file}")
    print(f"FastAPI file: {fastapi_file}")

    flask_data = load_json(flask_file)
    fastapi_data = load_json(fastapi_file)

    # Run comparisons
    counts_ok = compare_counts(flask_data, fastapi_data)
    names_ok = compare_indicator_names(flask_data, fastapi_data)
    values_ok = compare_values(flask_data, fastapi_data)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Counts match:     {'✅ PASS' if counts_ok else '❌ FAIL'}")
    print(f"Names match:      {'✅ PASS' if names_ok else '❌ FAIL'}")
    print(f"Values match:     {'✅ PASS' if values_ok else '❌ FAIL'}")

    all_ok = counts_ok and names_ok and values_ok

    print(f"\n{'='*60}")
    if all_ok:
        print("✅ VALIDATION PASSED - FastAPI implementation matches Flask")
        print("   You can proceed with Commit 7 (switch default flag)")
    else:
        print("❌ VALIDATION FAILED - Fix issues before proceeding")
        print("   Rollback to Flask mode: export CRYPTO_TOOLBOX_NEW=0")
    print(f"{'='*60}\n")

    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
