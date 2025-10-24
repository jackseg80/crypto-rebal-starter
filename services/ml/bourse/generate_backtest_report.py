"""
Generate HTML report from backtest results

Usage:
    python -m services.ml.bourse.generate_backtest_report

Reads data/backtest_results.json and generates static/backtest_report.html
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stop Loss Backtest Report</title>
    <style>
        :root {{
            --primary: #3b82f6;
            --success: #22c55e;
            --danger: #ef4444;
            --warning: #f59e0b;
            --bg: #f9fafb;
            --surface: #ffffff;
            --border: #e5e7eb;
            --text: #1f2937;
            --text-muted: #6b7280;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary) 0%, #1e40af 100%);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
        }}

        header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        header p {{
            opacity: 0.9;
            font-size: 0.95rem;
        }}

        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
        }}

        .card-title {{
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .card-value {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}

        .card-subtitle {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .positive {{ color: var(--success); }}
        .negative {{ color: var(--danger); }}
        .neutral {{ color: var(--text-muted); }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 2rem;
        }}

        thead {{
            background: var(--bg);
        }}

        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            font-weight: 600;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}

        tbody tr:hover {{
            background: var(--bg);
        }}

        tbody tr:last-child td {{
            border-bottom: none;
        }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .badge-success {{
            background: color-mix(in srgb, var(--success) 15%, transparent);
            color: var(--success);
        }}

        .badge-danger {{
            background: color-mix(in srgb, var(--danger) 15%, transparent);
            color: var(--danger);
        }}

        .section {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
        }}

        .section-title {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
        }}

        .verdict {{
            background: var(--bg);
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid var(--primary);
            margin-top: 1rem;
        }}

        .verdict strong {{
            display: block;
            margin-bottom: 0.5rem;
            color: var(--primary);
        }}

        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Stop Loss Backtest Report</h1>
            <p>ATR 2x vs Fixed % Performance Comparison</p>
            <p style="font-size: 0.875rem; margin-top: 0.5rem;">Generated: {timestamp}</p>
        </header>

        <!-- Configuration -->
        <div class="section">
            <h2 class="section-title">⚙️ Test Configuration</h2>
            <p><strong>Market Regime:</strong> {market_regime}</p>
            <p><strong>Timeframe:</strong> {timeframe}</p>
            <p><strong>Lookback Period:</strong> {lookback_days} days</p>
            <p><strong>Entry Interval:</strong> {entry_interval_days} days</p>
            <p><strong>Assets Tested:</strong> {assets_list}</p>
        </div>

        <!-- Aggregate Summary -->
        <div class="section">
            <h2 class="section-title">🎯 Aggregate Results</h2>

            <div class="summary-cards">
                <div class="card">
                    <div class="card-title">Overall Winner</div>
                    <div class="card-value {winner_class}">{overall_winner}</div>
                    <div class="card-subtitle">Based on total P&L</div>
                </div>

                <div class="card">
                    <div class="card-title">P&L Difference</div>
                    <div class="card-value {pnl_class}">${pnl_difference:,.0f}</div>
                    <div class="card-subtitle">{pnl_improvement_pct:+.1f}% improvement</div>
                </div>

                <div class="card">
                    <div class="card-title">ATR 2x Total P&L</div>
                    <div class="card-value">${atr_total_pnl:,.0f}</div>
                    <div class="card-subtitle">{atr_assets_won} assets won</div>
                </div>

                <div class="card">
                    <div class="card-title">Fixed % Total P&L</div>
                    <div class="card-value">${fixed_total_pnl:,.0f}</div>
                    <div class="card-subtitle">{fixed_assets_won} assets won</div>
                </div>
            </div>

            <div class="verdict">
                <strong>📝 Overall Verdict:</strong>
                {overall_verdict}
            </div>
        </div>

        <!-- Individual Results Table -->
        <div class="section">
            <h2 class="section-title">📈 Individual Asset Results</h2>

            <table>
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Period</th>
                        <th>ATR P&L</th>
                        <th>Fixed P&L</th>
                        <th>Difference</th>
                        <th>Winner</th>
                    </tr>
                </thead>
                <tbody>
                    {asset_rows}
                </tbody>
            </table>
        </div>

        <!-- Detailed Metrics Table -->
        <div class="section">
            <h2 class="section-title">📊 Detailed Metrics Comparison</h2>

            <table>
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Method</th>
                        <th>Trades</th>
                        <th>Win Rate</th>
                        <th>Stops Hit</th>
                        <th>Targets</th>
                        <th>Avg P&L %</th>
                    </tr>
                </thead>
                <tbody>
                    {metrics_rows}
                </tbody>
            </table>
        </div>

        <footer>
            <p>🤖 Generated by Crypto Rebal Starter - Stop Loss Backtesting Module</p>
            <p>Data source: Cached parquet files (data/cache/bourse/)</p>
        </footer>
    </div>
</body>
</html>
"""


def generate_html_report(results_file: str = "data/backtest_results.json", output_file: str = "static/backtest_report.html"):
    """
    Generate HTML report from JSON results

    Args:
        results_file: Path to JSON results file
        output_file: Path to output HTML file
    """
    try:
        # Load results
        with open(results_file, 'r') as f:
            results = json.load(f)

        config = results.get('test_config', {})
        aggregate = results.get('aggregate', {})
        individual = results.get('individual_results', [])

        # Extract aggregate data
        atr_agg = aggregate.get('atr_2x', {})
        fixed_agg = aggregate.get('fixed_pct', {})

        # Generate asset rows
        asset_rows = []
        for result in individual:
            symbol = result['symbol']
            period = result['data_period']
            atr = result['atr_2x']
            fixed = result['fixed_pct']
            comp = result['comparison']

            winner_badge = f'<span class="badge badge-success">{comp["winner"]}</span>' if comp['winner'] == 'ATR 2x' else f'<span class="badge badge-danger">{comp["winner"]}</span>'

            diff = comp['pnl_difference_usd']
            diff_class = 'positive' if diff > 0 else 'negative'

            asset_rows.append(f"""
                <tr>
                    <td><strong>{symbol}</strong></td>
                    <td>{period['start']} to {period['end']}<br><small>{period['days']} days</small></td>
                    <td class="{'positive' if atr['total_pnl_usd'] > 0 else 'negative'}">${atr['total_pnl_usd']:,.0f}</td>
                    <td class="{'positive' if fixed['total_pnl_usd'] > 0 else 'negative'}">${fixed['total_pnl_usd']:,.0f}</td>
                    <td class="{diff_class}">${diff:+,.0f}</td>
                    <td>{winner_badge}</td>
                </tr>
            """)

        # Generate metrics rows (detailed)
        metrics_rows = []
        for result in individual:
            symbol = result['symbol']
            atr = result['atr_2x']
            fixed = result['fixed_pct']

            # ATR row
            metrics_rows.append(f"""
                <tr>
                    <td rowspan="2"><strong>{symbol}</strong></td>
                    <td>ATR 2x</td>
                    <td>{atr['total_trades']}</td>
                    <td>{atr['win_rate']*100:.1f}%</td>
                    <td>{atr['stops_hit_pct']*100:.1f}%</td>
                    <td>{atr['targets_reached_pct']*100:.1f}%</td>
                    <td class="{'positive' if atr['avg_pnl_pct'] > 0 else 'negative'}">{atr['avg_pnl_pct']*100:+.2f}%</td>
                </tr>
            """)

            # Fixed row
            metrics_rows.append(f"""
                <tr>
                    <td>Fixed %</td>
                    <td>{fixed['total_trades']}</td>
                    <td>{fixed['win_rate']*100:.1f}%</td>
                    <td>{fixed['stops_hit_pct']*100:.1f}%</td>
                    <td>{fixed['targets_reached_pct']*100:.1f}%</td>
                    <td class="{'positive' if fixed['avg_pnl_pct'] > 0 else 'negative'}">{fixed['avg_pnl_pct']*100:+.2f}%</td>
                </tr>
            """)

        # Generate overall verdict
        pnl_improvement = aggregate.get('pnl_improvement_pct', 0)
        if abs(pnl_improvement) < 5:
            overall_verdict = "Both methods perform similarly (< 5% difference). No clear winner."
        elif pnl_improvement > 0:
            overall_verdict = f"ATR 2x significantly outperforms Fixed % by {pnl_improvement:.1f}%. <strong>Recommendation: Use ATR 2x as default method.</strong>"
        else:
            overall_verdict = f"Fixed % outperforms ATR 2x by {abs(pnl_improvement):.1f}%. Further investigation needed to understand why ATR underperforms."

        # Fill template
        html = HTML_TEMPLATE.format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            market_regime=config.get('market_regime', 'N/A'),
            timeframe=config.get('timeframe', 'N/A'),
            lookback_days=config.get('lookback_days', 0),
            entry_interval_days=config.get('entry_interval_days', 0),
            assets_list=', '.join(config.get('symbols', [])),
            overall_winner=aggregate.get('overall_winner', 'N/A'),
            winner_class='positive' if aggregate.get('overall_winner') == 'ATR 2x' else 'negative',
            pnl_difference=aggregate.get('pnl_difference_usd', 0),
            pnl_class='positive' if aggregate.get('pnl_difference_usd', 0) > 0 else 'negative',
            pnl_improvement_pct=pnl_improvement,
            atr_total_pnl=atr_agg.get('total_pnl_usd', 0),
            atr_assets_won=atr_agg.get('assets_won', 0),
            fixed_total_pnl=fixed_agg.get('total_pnl_usd', 0),
            fixed_assets_won=fixed_agg.get('assets_won', 0),
            overall_verdict=overall_verdict,
            asset_rows=''.join(asset_rows),
            metrics_rows=''.join(metrics_rows)
        )

        # Write to file
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"✅ HTML report generated: {output_file}")
        print(f"\n✅ HTML report generated successfully!")
        print(f"📄 Open in browser: file:///{Path(output_file).absolute()}")

    except FileNotFoundError:
        logger.error(f"Results file not found: {results_file}")
        print(f"\n❌ Error: Results file not found: {results_file}")
        print(f"💡 Run the backtest first: python -m services.ml.bourse.test_backtest")
    except Exception as e:
        logger.error(f"Failed to generate report: {e}", exc_info=True)
        print(f"\n❌ Error generating report: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_html_report()
