import asyncio
from api.unified_data import get_unified_filtered_balances
from services.risk_management import risk_manager

async def main():
    data = await get_unified_filtered_balances(source='stub', min_usd=1.0)
    items = data.get('items', [])
    print('items', len(items))
    holdings = []
    for it in items:
        if float(it.get('value_usd') or 0) > 0:
            holdings.append({'symbol': it.get('symbol',''), 'balance': float(it.get('amount') or 0), 'value_usd': float(it.get('value_usd') or 0)})
    print('holdings', len(holdings))
    m = await risk_manager.calculate_portfolio_risk_metrics(holdings=holdings, price_history_days=30)
    print('metrics ok', m.var_95_1d, m.sharpe_ratio)
    c = await risk_manager.calculate_correlation_matrix(holdings=holdings, lookback_days=30)
    print('corr ok', len(c.correlations))

asyncio.run(main())
