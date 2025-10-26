"""
Script de validation des recommandations pour l'utilisateur Jack
Vérifie la cohérence des recommandations avec les données réelles du marché
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any
import asyncio

from services.ml.bourse.data_sources import StocksDataSource


class RecommendationsValidator:
    """Valide les recommandations générées par le système"""

    def __init__(self):
        self.data_source = StocksDataSource()
        self.validation_results = []

    async def validate_recommendations(
        self,
        recs_file: str,
        positions_file: str
    ) -> Dict[str, Any]:
        """
        Valide les recommandations contre les données réelles

        Args:
            recs_file: Path to recommendations JSON file
            positions_file: Path to positions CSV file

        Returns:
            Dict with validation results
        """
        # Load recommendations
        with open(recs_file, 'r', encoding='utf-8') as f:
            recs_data = json.load(f)

        recommendations = recs_data.get('recommendations', [])
        print(f"\n[*] Validation de {len(recommendations)} recommandations...")
        print(f"[*] Generees le: {recs_data.get('generated_at')}")
        print(f"[*] Regime de marche: {recs_data.get('market_regime')}")
        print(f"[*] Timeframe: {recs_data.get('timeframe')}")

        # Load positions
        positions_df = pd.read_csv(positions_file, encoding='utf-8-sig')
        print(f"\n[*] Positions CSV charge: {len(positions_df)} lignes")

        # Extract actual prices from CSV
        actual_prices = self._extract_prices_from_csv(positions_df)

        # Validate each recommendation
        validation_summary = {
            'total_validated': 0,
            'price_matches': 0,
            'price_mismatches': 0,
            'technical_checks': 0,
            'stop_loss_checks': 0,
            'risk_reward_valid': 0,
            'risk_reward_invalid': 0,
            'details': []
        }

        for rec in recommendations:
            symbol = rec['symbol']
            print(f"\n{'='*60}")
            print(f"Validation: {symbol} ({rec['name']})")
            print(f"{'='*60}")

            result = await self._validate_recommendation(rec, actual_prices)
            self.validation_results.append(result)

            # Update summary
            validation_summary['total_validated'] += 1
            if result['price_valid']:
                validation_summary['price_matches'] += 1
            else:
                validation_summary['price_mismatches'] += 1

            if result['technical_valid']:
                validation_summary['technical_checks'] += 1

            if result['stop_loss_valid']:
                validation_summary['stop_loss_checks'] += 1

            if result.get('risk_reward_valid'):
                validation_summary['risk_reward_valid'] += 1
            else:
                validation_summary['risk_reward_invalid'] += 1

            validation_summary['details'].append(result)

        return validation_summary

    async def _validate_recommendation(
        self,
        rec: Dict[str, Any],
        actual_prices: Dict[str, float]
    ) -> Dict[str, Any]:
        """Validate a single recommendation"""
        symbol = rec['symbol']
        rec_price = rec['price_targets'].get('current_price')
        actual_price = actual_prices.get(symbol)

        result = {
            'symbol': symbol,
            'action': rec['action'],
            'confidence': rec['confidence'],
            'score': rec['score'],
            'price_valid': False,
            'price_diff_pct': None,
            'technical_valid': False,
            'stop_loss_valid': False,
            'risk_reward_valid': False,
            'issues': []
        }

        # 1. Validate price
        if actual_price and rec_price:
            price_diff_pct = abs((actual_price - rec_price) / rec_price) * 100
            result['price_diff_pct'] = round(price_diff_pct, 2)
            result['rec_price'] = rec_price
            result['actual_price'] = actual_price

            # Price should be within 5% (recommendations from previous day)
            if price_diff_pct <= 5.0:
                result['price_valid'] = True
                print(f"[OK] Prix: Recommandation ${rec_price:.2f} vs Reel ${actual_price:.2f} (diff: {price_diff_pct:.2f}%)")
            else:
                result['issues'].append(f"Prix diverge de {price_diff_pct:.2f}%")
                print(f"[!!] Prix: Recommandation ${rec_price:.2f} vs Reel ${actual_price:.2f} (diff: {price_diff_pct:.2f}%)")
        else:
            result['issues'].append("Prix manquant dans CSV ou recommandations")
            print(f"[X] Prix: Donnees manquantes (Rec: {rec_price}, Reel: {actual_price})")

        # 2. Validate technical indicators (fetch fresh data)
        print(f"\n[*] Validation des indicateurs techniques...")

        # Extract ISIN and exchange hint from position data if available
        isin = None
        exchange_hint = None

        # Try to get from recommendations metadata (if present)
        # For now, we'll let the detector auto-detect from symbol

        try:
            hist_data = await self.data_source.get_ohlcv_data(
                symbol=symbol,
                lookback_days=90,
                isin=isin,
                exchange_hint=exchange_hint
            )

            if hist_data is not None and len(hist_data) >= 20:
                # RSI
                rec_rsi = rec['technical'].get('rsi_14d')
                actual_rsi = self._calculate_rsi(hist_data['close'], 14)

                if rec_rsi and actual_rsi:
                    rsi_diff = abs(rec_rsi - actual_rsi)
                    print(f"  RSI: Recommandation {rec_rsi:.1f} vs Calculé {actual_rsi:.1f} (diff: {rsi_diff:.1f})")

                    if rsi_diff <= 15:  # RSI can change ~10-15 points in a day
                        result['technical_valid'] = True
                    else:
                        result['issues'].append(f"RSI diverge de {rsi_diff:.1f} points")

                # MA50
                rec_ma50_pct = rec['technical'].get('vs_ma50_pct')
                if rec_ma50_pct is not None and len(hist_data) >= 50:
                    ma50 = hist_data['close'].rolling(50).mean().iloc[-1]
                    current_price = hist_data['close'].iloc[-1]
                    actual_ma50_pct = ((current_price - ma50) / ma50) * 100

                    ma50_diff = abs(rec_ma50_pct - actual_ma50_pct)
                    print(f"  MA50: Recommandation {rec_ma50_pct:.1f}% vs Calculé {actual_ma50_pct:.1f}% (diff: {ma50_diff:.1f}%)")

        except Exception as e:
            result['issues'].append(f"Erreur validation technique: {str(e)}")
            print(f"  [!!] Erreur fetch donnees: {e}")

        # 3. Validate stop loss
        stop_loss_analysis = rec['price_targets'].get('stop_loss_analysis', {})
        recommended_sl = stop_loss_analysis.get('recommended', {})

        if recommended_sl:
            sl_price = recommended_sl.get('price')
            sl_pct = recommended_sl.get('distance_pct')
            quality = recommended_sl.get('quality')

            print(f"\n[*] Stop Loss: ${sl_price:.2f} ({sl_pct:.1f}%) - Quality: {quality}")

            if quality == 'high':
                result['stop_loss_valid'] = True
            else:
                result['issues'].append(f"Stop loss quality {quality} (expected: high)")

        # 4. Validate Risk/Reward
        price_targets = rec['price_targets']
        rr_tp1 = price_targets.get('risk_reward_tp1')
        rr_tp2 = price_targets.get('risk_reward_tp2')

        if rr_tp1 is not None and rr_tp2 is not None:
            print(f"\n[*] Risk/Reward: TP1={rr_tp1:.2f}, TP2={rr_tp2:.2f}")

            if rr_tp1 >= 1.5:
                result['risk_reward_valid'] = True
                print(f"  [OK] R/R ratio valide (>=1.5)")
            else:
                result['issues'].append(f"R/R ratio insuffisant: {rr_tp1}")
                print(f"  [!!] R/R ratio < 1.5")
        else:
            print(f"\n[*] Risk/Reward: N/A (action = {rec['action']})")
            # For HOLD positions, R/R is not applicable
            if rec['action'] in ['HOLD', 'SELL', 'STRONG SELL']:
                result['risk_reward_valid'] = True  # Don't penalize HOLD for missing R/R

        # Summary
        if result['issues']:
            print(f"\n[!!] Issues detectees:")
            for issue in result['issues']:
                print(f"  - {issue}")

        return result

    def _extract_prices_from_csv(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extract current prices from Saxo CSV"""
        import re

        prices = {}

        for _, row in df.iterrows():
            # Look for rows with symbol pattern like 'TSLA:xnas' in any column
            symbol_found = None
            for col_value in row.values:
                if isinstance(col_value, str) and ':x' in col_value and len(str(col_value).split(':')) == 2:
                    symbol_full = col_value
                    symbol_found = symbol_full.split(':')[0]
                    break

            if symbol_found:
                # Try to find price in various columns
                # NOTE: Due to CSV parsing offset (newline in "Statut"),
                # "Prix entrée" actually contains the current market price!
                price_value = None
                for price_col in ['Prix entrée']:
                    if price_col in row.index and pd.notna(row[price_col]):
                        try:
                            # Clean value
                            val = str(row[price_col]).replace(',', '.').replace(' ', '').replace('\u202f', '')
                            # Remove currency symbols
                            val = re.sub(r'[€$]', '', val)
                            price = float(val)
                            if price > 0 and price < 100000:  # Reasonable price range
                                price_value = price
                                break
                        except:
                            pass

                if price_value:
                    prices[symbol_found] = price_value

        print(f"\n[*] Prix extraits du CSV: {len(prices)} symboles")
        for sym, price in sorted(prices.items()):
            print(f"  {sym}: ${price:.2f}")

        return prices

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    def generate_report(self, summary: Dict[str, Any]) -> str:
        """Generate validation report"""
        report = "\n" + "="*80 + "\n"
        report += "RAPPORT DE VALIDATION DES RECOMMANDATIONS\n"
        report += "="*80 + "\n\n"

        report += f"Total valide: {summary['total_validated']}\n"
        report += f"Prix correspondants: {summary['price_matches']} ({summary['price_matches']/summary['total_validated']*100:.1f}%)\n"
        report += f"Prix divergents: {summary['price_mismatches']} ({summary['price_mismatches']/summary['total_validated']*100:.1f}%)\n"
        report += f"Indicateurs techniques valides: {summary['technical_checks']}\n"
        report += f"Stop loss valides: {summary['stop_loss_checks']}\n"
        report += f"R/R ratios valides (>=1.5): {summary['risk_reward_valid']}\n"
        report += f"R/R ratios insuffisants: {summary['risk_reward_invalid']}\n\n"

        # Detailed issues
        report += "="*80 + "\n"
        report += "DETAILS DES PROBLEMES DETECTES\n"
        report += "="*80 + "\n\n"

        for detail in summary['details']:
            if detail['issues']:
                report += f"\n{detail['symbol']} ({detail['action']}):\n"
                for issue in detail['issues']:
                    report += f"  [X] {issue}\n"

        return report


async def main():
    """Main validation function"""
    validator = RecommendationsValidator()

    recs_file = "d:/Python/crypto-rebal-starter/long_recs.json"
    positions_file = "d:/Python/crypto-rebal-starter/data/users/jack/saxobank/data/20251025_103840_Positions_25-oct.-2025_10_37_13.csv"

    print("\n" + "="*80)
    print("VALIDATION DES RECOMMANDATIONS - USER: jack")
    print("="*80)

    summary = await validator.validate_recommendations(recs_file, positions_file)

    # Generate report
    report = validator.generate_report(summary)
    print("\n" + report)

    # Save report to file
    report_file = "d:/Python/crypto-rebal-starter/validation_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n[*] Rapport sauvegarde dans: {report_file}")

    return summary


if __name__ == "__main__":
    asyncio.run(main())
