import pandas as pd
import json

csv_file = 'data/users/jack/saxobank/data/20251025_103840_Positions_25-oct.-2025_10_37_13.csv'
recs_file = 'long_recs.json'

df = pd.read_csv(csv_file, encoding='utf-8-sig')

print('='*80)
print('EXTRACTION DES PRIX CORRECTS DU CSV SAXO')
print('='*80 + '\n')

prices = {}

for idx, row in df.iterrows():
    symbol_value = row.get('Date de valeur', '')
    
    if symbol_value and isinstance(symbol_value, str) and ':' in symbol_value:
        symbol = symbol_value.split(':')[0]
        val_actuelle = row.get('Val. actuelle')
        
        if pd.notna(val_actuelle) and isinstance(val_actuelle, (int, float)):
            price = float(val_actuelle)
            
            if symbol not in prices:
                prices[symbol] = price
                print(f'{symbol:6s}: ${price:10.2f}')
            else:
                print(f'{symbol:6s}: ${price:10.2f} (DUPE - skipped, keeping ${prices[symbol]:.2f})')

print(f'\n{len(prices)} prices extracted\n')

with open(recs_file, 'r', encoding='utf-8') as f:
    recs_data = json.load(f)

recommendations = recs_data.get('recommendations', [])

print('='*80)
print('COMPARAISON PRIX CSV vs RECOMMANDATIONS')
print('='*80 + '\n')

matches = 0
mismatches = 0

for rec in recommendations:
    symbol = rec['symbol']
    rec_price = rec['price_targets'].get('current_price')
    csv_price = prices.get(symbol)
    
    if csv_price and rec_price:
        diff_pct = abs((csv_price - rec_price) / rec_price) * 100
        
        if diff_pct <= 5.0:
            status = '[OK]'
            matches += 1
        else:
            status = '[!!]'
            mismatches += 1
            
        print(f'{status} {symbol:6s}: Rec ${rec_price:7.2f} vs CSV ${csv_price:7.2f} (diff: {diff_pct:5.1f}%)')

print(f'\n{matches} matches ({matches*100/(matches+mismatches):.1f}%), {mismatches} mismatches ({mismatches*100/(matches+mismatches):.1f}%)')
