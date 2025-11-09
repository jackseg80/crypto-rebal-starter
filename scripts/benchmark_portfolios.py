"""
Benchmark script - Compare 3 portfolios with metrics calculated DIRECTLY from CSV
No backend dependency - all calculations done locally
User: jack, Portfolios: Low_Risk_Contra.csv, Medium_Risk_Contra.csv, High_Risk_Contra.csv
"""

import csv
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import constants for asset classification
from shared.asset_groups import ASSET_GROUPS

# Configuration
USER_ID = "jack"
PORTFOLIOS = [
    "Low_Risk_Contra.csv",
    "Medium_Risk_Contra.csv",
    "High_Risk_Contra.csv"
]

# Paths
DATA_DIR = project_root / "data" / "users" / USER_ID / "cointracking" / "uploads"
OUTPUT_CSV = project_root / "data" / "benchmark_results.csv"


def load_csv_balances(csv_path: Path) -> List[Dict[str, Any]]:
    """Load balances from CSV file and normalize format"""
    balances = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse CSV format: Currency,Amount,Price (USD),Value (USD),Exchange
            symbol = row.get('Currency', '').strip().upper()
            if not symbol:
                continue

            amount = float(row.get('Amount', 0))
            value_usd = float(row.get('Value (USD)', 0))
            location = row.get('Exchange', 'Unknown')

            balances.append({
                'symbol': symbol,
                'alias': symbol,
                'amount': amount,
                'value_usd': value_usd,
                'location': location
            })

    return balances


def classify_asset(symbol: str) -> str:
    """Classify asset into group using constants"""
    for group_name, assets in ASSET_GROUPS.items():
        if symbol in assets:
            return group_name
    return "Others"


def calculate_metrics(portfolio_name: str, balances: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate all metrics for a portfolio"""

    # Basic portfolio metrics
    total_value = sum(b['value_usd'] for b in balances)
    asset_count = len(balances)

    # Group distribution
    groups = {}
    for balance in balances:
        group = classify_asset(balance['symbol'])
        if group not in groups:
            groups[group] = {'value': 0, 'count': 0}
        groups[group]['value'] += balance['value_usd']
        groups[group]['count'] += 1

    group_count = len(groups)

    # Concentration metrics
    if balances:
        sorted_balances = sorted(balances, key=lambda x: x['value_usd'], reverse=True)
        top_holding = sorted_balances[0]
        top_holding_pct = (top_holding['value_usd'] / total_value * 100) if total_value > 0 else 0
        top_holding_symbol = top_holding['symbol']

        # HHI (Herfindahl-Hirschman Index)
        hhi = sum((b['value_usd'] / total_value) ** 2 for b in balances) if total_value > 0 else 0
    else:
        top_holding_pct = 0
        top_holding_symbol = None
        hhi = 0

    # Diversity score (simple: number of groups with > 5% allocation)
    diversity_score = sum(1 for g in groups.values() if (g['value'] / total_value) > 0.05) if total_value > 0 else 0

    # Group percentages
    group_pcts = {name: (data['value'] / total_value * 100) if total_value > 0 else 0
                  for name, data in groups.items()}

    # Stable vs Risky split
    stable_groups = {'Stablecoins'}
    stables_pct = sum(pct for group, pct in group_pcts.items() if group in stable_groups)
    risky_pct = 100 - stables_pct

    # Risk score estimation (simplified)
    # CONVENTION RISK SCORING (CLAUDE.md):
    # - Robustness Score: 0-100, higher = better portfolio
    # - Penalty Score: 0-100, higher = worse portfolio
    #
    # Calculate penalty factors (higher = worse)
    stables_factor = max(0, 100 - stables_pct)  # 0-100, lower stables = higher penalty
    concentration_factor = hhi * 100  # 0-100, higher concentration = higher penalty

    # Calculate total portfolio penalty (higher = worse)
    portfolio_penalty = stables_factor * 0.3 + concentration_factor * 0.7

    # Convert penalty to robustness score (higher = better) - INVERSION REQUIRED HERE
    robustness_score = 100 - portfolio_penalty
    robustness_score = max(0, min(100, robustness_score))  # Clamp to 0-100

    # Legacy alias for compatibility
    risk_score = robustness_score

    # Build comprehensive metrics dict
    metrics = {
        'portfolio': portfolio_name,

        # Basic metrics
        'asset_count': asset_count,
        'group_count': group_count,
        'total_value_usd': round(total_value, 2),
        'diversity_score': diversity_score,

        # Top holding
        'top_holding_symbol': top_holding_symbol,
        'top_holding_pct': round(top_holding_pct, 2),

        # Concentration
        'concentration_hhi': round(hhi, 4),

        # Risk estimation
        'risk_score_estimated': round(risk_score, 2),
        'stables_pct': round(stables_pct, 2),
        'risky_pct': round(risky_pct, 2),
    }

    # Add group distributions
    for group, pct in group_pcts.items():
        metrics[f'group_{group}_pct'] = round(pct, 2)
        metrics[f'group_{group}_value'] = round(groups[group]['value'], 2)

    # Add asset list
    asset_symbols = [b['symbol'] for b in sorted(balances, key=lambda x: x['value_usd'], reverse=True)]
    metrics['assets'] = ', '.join(asset_symbols)

    return metrics


def run_benchmark():
    """Main benchmark function - calculate all metrics locally"""
    print("=" * 80)
    print("BENCHMARK - 3 Portfolios Comparison (Local Calculation)")
    print(f"User: {USER_ID}")
    print("=" * 80)

    results = []

    for idx, portfolio_name in enumerate(PORTFOLIOS):
        print(f"\n[{idx+1}/{len(PORTFOLIOS)}] Processing: {portfolio_name}")

        # Load CSV
        csv_path = DATA_DIR / portfolio_name
        if not csv_path.exists():
            print(f"[X] File not found: {csv_path}")
            continue

        print(f"[+] Loading CSV: {csv_path}")
        balances = load_csv_balances(csv_path)
        print(f"[+] Loaded {len(balances)} assets")

        # Calculate metrics
        print(f"[+] Calculating metrics...")
        metrics = calculate_metrics(portfolio_name, balances)
        results.append(metrics)

        # Show summary
        print(f"[OK] {metrics['asset_count']} assets, ${metrics['total_value_usd']:,.0f}, "
              f"{metrics['group_count']} groups, Risk Score: {metrics['risk_score_estimated']:.0f}")

    # Write CSV in LONG format (1 row per metric x portfolio)
    if not results:
        print("[X] No results to write")
        return

    print(f"\n[+] Writing CSV in LONG format to: {OUTPUT_CSV}")

    # Convert to long format: portfolio, metric, value
    long_rows = []

    for result in results:
        portfolio_name = result['portfolio']
        for metric_name, metric_value in result.items():
            if metric_name == 'portfolio':
                continue

            long_rows.append({
                'portfolio': portfolio_name,
                'metric': metric_name,
                'value': metric_value
            })

    # Write long format
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['portfolio', 'metric', 'value'])
        writer.writeheader()
        writer.writerows(long_rows)

    print(f"[OK] Benchmark complete!")
    print(f"[INFO] {len(results)} portfolios x {len(long_rows)} rows (long format)")
    print(f"[INFO] Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    run_benchmark()
