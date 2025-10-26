"""
Script pour générer un rapport de validation complet des recommandations
"""

import json
import pandas as pd

# Load recommendations
with open('new_recommendations_25oct.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

recommendations = data.get('recommendations', [])

print('='*80)
print('RAPPORT DE VALIDATION DES RECOMMANDATIONS - 25 OCT 2025')
print('='*80)
print(f'\nTotal: {len(recommendations)} recommandations generees')
print(f'Marche: {data.get("market_regime", "N/A")}')
print(f'Source: User jack, CSV Saxo 25 oct 2025')

# Analyze actions distribution
actions = {}
for rec in recommendations:
    action = rec['action']
    actions[action] = actions.get(action, 0) + 1

print(f'\nDistribution des actions:')
for action, count in sorted(actions.items(), key=lambda x: -x[1]):
    print(f'  {action:12s}: {count:2d} ({count*100/len(recommendations):.1f}%)')

# Sector concentration
sectors = {}
for rec in recommendations:
    sector = rec.get('sector', 'Unknown')
    value = rec.get('current_value', 0)
    if sector not in sectors:
        sectors[sector] = {'count': 0, 'value': 0}
    sectors[sector]['count'] += 1
    sectors[sector]['value'] += value

total_value = sum(s['value'] for s in sectors.values())

print(f'\nConcentration sectorielle:')
for sector, data in sorted(sectors.items(), key=lambda x: -x[1]['value']):
    pct = data['value'] * 100 / total_value if total_value > 0 else 0
    print(f'  {sector:15s}: {data["count"]:2d} assets, ${data["value"]:10,.0f} ({pct:.1f}%)')

# Technical indicators summary
rsi_oversold = sum(1 for r in recommendations if r['technical'].get('rsi_14d', 50) < 30)
rsi_overbought = sum(1 for r in recommendations if r['technical'].get('rsi_14d', 50) > 70)
above_ma50 = sum(1 for r in recommendations if r['technical'].get('vs_ma50_pct', 0) > 5)
macd_bullish = sum(1 for r in recommendations if r['technical'].get('macd_signal') == 'bullish')

print(f'\nIndicateurs techniques:')
print(f'  RSI < 30 (oversold):     {rsi_oversold:2d}')
print(f'  RSI > 70 (overbought):   {rsi_overbought:2d}')
print(f'  Prix > MA50 +5%%:        {above_ma50:2d}')
print(f'  MACD bullish:            {macd_bullish:2d}/{len(recommendations)}')

# Adjustments analysis
adjusted = sum(1 for r in recommendations if r.get('adjusted', False))
sector_limit = sum(1 for r in recommendations if r.get('adjustment_reason') == 'sector_concentration')

print(f'\nAjustements:')
print(f'  Recommandations ajustees: {adjusted}/{len(recommendations)} ({adjusted*100/len(recommendations):.1f}%)')
print(f'  Raison: Limite sectorielle: {sector_limit}')

# Stop loss analysis
stop_methods = {}
for rec in recommendations:
    sl_method = rec['price_targets'].get('stop_loss_analysis', {}).get('recommended_method', 'N/A')
    stop_methods[sl_method] = stop_methods.get(sl_method, 0) + 1

print(f'\nStop loss methods:')
for method, count in sorted(stop_methods.items(), key=lambda x: -x[1]):
    print(f'  {method:20s}: {count:2d}')

# Risk/Reward analysis
good_rr = sum(1 for r in recommendations if r['price_targets'].get('risk_reward_tp1', 0) >= 1.5)
excellent_rr = sum(1 for r in recommendations if r['price_targets'].get('risk_reward_tp1', 0) >= 2.0)

print(f'\nRisk/Reward ratios:')
print(f'  R/R >= 1.5 (bon):        {good_rr}/{len(recommendations)} ({good_rr*100/len(recommendations):.1f}%)')
print(f'  R/R >= 2.0 (excellent):  {excellent_rr}/{len(recommendations)} ({excellent_rr*100/len(recommendations):.1f}%)')

# Top recommendations by score
print(f'\nTop 10 recommandations (par score):')
sorted_recs = sorted(recommendations, key=lambda x: x['score'], reverse=True)
for i, rec in enumerate(sorted_recs[:10], 1):
    action = rec['action']
    symbol = rec['symbol']
    score = rec['score']
    confidence = rec['confidence']
    rr = rec['price_targets'].get('risk_reward_tp1', 0)
    
    # Add markers
    marker = ''
    if rec.get('adjusted'):
        marker = ' [ADJUSTED]'
    
    print(f'  {i:2d}. {symbol:6s} {action:12s} Score:{score:.2f} Conf:{confidence:.2f} R/R:{rr:.1f}{marker}')

