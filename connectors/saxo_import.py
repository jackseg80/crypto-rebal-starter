"""
Saxo Bank CSV/XLSX Import Connector
Handles import and processing of Saxo Bank export files
"""

import pandas as pd
import logging
from typing import Dict, List, Optional, Union
from pathlib import Path
import re
import unicodedata
from datetime import datetime

logger = logging.getLogger(__name__)

class SaxoImportConnector:
    """
    Connector for importing Saxo Bank CSV/XLSX files
    """

    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls']
        self.required_columns = ['Position ID', 'Instrument', 'Quantity', 'Market Value', 'Currency']
        self.optional_columns = ['Asset Class', 'Market', 'Exchange']
        self.column_aliases = {
            'instrument': 'Instrument',
            'instruments': 'Instrument',
            'symbol': 'Symbol',
            'symbole': 'Symbol',
            'quantity': 'Quantity',
            'quantite': 'Quantity',
            'quantites': 'Quantity',
            'qty': 'Quantity',
            'market value': 'Market Value',
            'market value usd': 'Market Value',
            'market value eur': 'Market Value',
            'valeur actuelle': 'Market Value',
            'valeur actuelle eur': 'Market Value',
            'valeur actuelle usd': 'Market Value',
            'valeur actuelle devise': 'Market Value',
            'currency': 'Currency',
            'devise': 'Currency',
            'monnaie': 'Currency',
            'asset class': 'Asset Class',
            'asset type': 'Asset Class',
            "type d'actif": 'Asset Class',
            'type d actif': 'Asset Class',
            'type dactif': 'Asset Class',
            'classe d actif': 'Asset Class',
            'position id': 'Position ID',
            'numero de position': 'Position ID',
            'no de position': 'Position ID',
            'n de position': 'Position ID',
        }

    def _canonical_column_name(self, name: str) -> str:
        base = unicodedata.normalize('NFKD', str(name or '')).encode('ascii', 'ignore').decode('ascii')
        base = base.lower().replace('\n', ' ').replace('\r', ' ')
        base = re.sub(r'[^a-z0-9]+', ' ', base)
        return ' '.join(base.split())

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]
        rename_map = {}
        seen = set()
        for column in df.columns:
            canonical = self._canonical_column_name(column)
            target = self.column_aliases.get(canonical)
            if target and target not in seen:
                rename_map[column] = target
                seen.add(target)
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    def _to_float(self, value: Union[str, int, float]) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            if pd.isna(value):
                return 0.0
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(' ', ' ').strip()
            cleaned = cleaned.replace(',', '.')
            cleaned = re.sub(r'[^0-9.\-]', '', cleaned)
            if cleaned in {'', '-', '.', '-.'}:
                return 0.0
            try:
                return float(cleaned)
            except ValueError as exc:
                raise ValueError(f"Unable to parse numeric value '{value}'") from exc
        if pd.isna(value):
            return 0.0
        raise ValueError(f'Unsupported numeric type: {type(value)}')

    def validate_file(self, file_path: Union[str, Path]) -> Dict[str, Union[bool, str]]:
        """
        Validate if file can be processed

        Returns:
            Dict with validation results
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return {"valid": False, "error": "File not found"}

        if file_path.suffix.lower() not in self.supported_formats:
            return {"valid": False, "error": f"Unsupported format. Supported: {', '.join(self.supported_formats)}"}

        try:
            df = self._load_file(file_path)
            missing_cols = [col for col in self.required_columns if col not in df.columns]

            if missing_cols:
                return {"valid": False, "error": f"Missing required columns: {', '.join(missing_cols)}"}

            return {"valid": True, "rows": len(df), "columns": list(df.columns)}

        except Exception as e:
            return {"valid": False, "error": f"Error reading file: {str(e)}"}

    def _load_file(self, file_path: Path) -> pd.DataFrame:
        """Load file into DataFrame"""
        if file_path.suffix.lower() == '.csv':
            # Try different encodings and separators
            for encoding in ['utf-8', 'iso-8859-1', 'cp1252']:
                for sep in [',', ';', '\t']:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                        if len(df.columns) > 1:  # Valid CSV should have multiple columns
                            return self._normalize_dataframe(df)
                    except:
                        continue
            raise ValueError("Could not read CSV file with any common encoding/separator")
        else:
            df = pd.read_excel(file_path)
            return self._normalize_dataframe(df)

    def process_saxo_file(self, file_path: Union[str, Path]) -> Dict[str, Union[List, Dict, str]]:
        """
        Process Saxo Bank export file and return standardized data

        Returns:
            Dict with processed positions and metadata
        """
        try:
            df = self._load_file(Path(file_path))
            logger.info(f"Processing Saxo file with {len(df)} positions")

            # Clean and standardize data
            positions = []
            errors = []

            for idx, row in df.iterrows():
                try:
                    position = self._process_position(row)
                    if position:
                        positions.append(position)
                except Exception as e:
                    errors.append(f"Row {idx + 1}: {str(e)}")
                    logger.warning(f"Error processing row {idx + 1}: {e}")

            return {
                "positions": positions,
                "total_positions": len(positions),
                "total_market_value_usd": sum(p.get("market_value_usd", 0) for p in positions),
                "currencies": list(set(p.get("currency", "USD") for p in positions)),
                "asset_classes": list(set(p.get("asset_class", "Unknown") for p in positions)),
                "errors": errors,
                "processed_at": datetime.now().isoformat(),
                "source": "saxo_bank"
            }

        except Exception as e:
            logger.error(f"Error processing Saxo file: {e}")
            return {
                "positions": [],
                "errors": [f"File processing failed: {str(e)}"],
                "processed_at": datetime.now().isoformat(),
                "source": "saxo_bank"
            }

    def _process_position(self, row: pd.Series) -> Optional[Dict]:
        """Process a single position row"""
        try:
            position_id = str(row.get('Position ID', '') or '').strip()
            instrument = str(row.get('Instrument', '') or '').strip()
            quantity = self._to_float(row.get('Quantity', 0))
            market_value = self._to_float(row.get('Market Value', 0))
            currency = str(row.get('Currency', 'USD') or 'USD').strip().upper()
            asset_class_raw = str(row.get('Asset Class', 'Unknown') or 'Unknown')

            if not instrument or quantity == 0:
                return None

            symbol = self._standardize_symbol(instrument)
            market_value_usd = self._convert_to_usd(market_value, currency)

            return {
                "position_id": position_id or symbol,
                "symbol": symbol,
                "instrument": instrument,
                "name": instrument or symbol,
                "quantity": quantity,
                "market_value": market_value,
                "market_value_usd": market_value_usd,
                "currency": currency,
                "asset_class": self._standardize_asset_class(asset_class_raw),
                "source": "saxo_bank",
                "import_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            raise ValueError(f"Invalid position data: {e}")

    def _standardize_symbol(self, instrument: str) -> str:
        """Standardize instrument symbols"""
        # Handle ISIN format
        if instrument.startswith('ISIN:'):
            isin = instrument.replace('ISIN:', '')
            # Map common ISINs to symbols (placeholder)
            isin_map = {
                'IE00B4L5Y983': 'IWDA',  # iShares Core MSCI World
                'IE00B3RBWM25': 'VWRL',  # Vanguard FTSE All-World
                'US0378331005': 'AAPL',  # Apple Inc
                'US5949181045': 'MSFT'   # Microsoft
            }
            return isin_map.get(isin, isin)

        # Clean ticker symbols
        symbol = re.sub(r'[^\w.]', '', instrument).upper()
        return symbol if symbol else instrument

    def _standardize_asset_class(self, asset_class: str) -> str:
        """Standardize asset class names"""
        asset_class = asset_class.lower().strip()

        mapping = {
            'equity': 'Stock',
            'stock': 'Stock',
            'etf': 'ETF',
            'exchange traded fund': 'ETF',
            'bond': 'Bond',
            'fixed income': 'Bond',
            'option': 'Option',
            'warrant': 'Warrant',
            'fund': 'Fund',
            'mutual fund': 'Fund'
        }

        return mapping.get(asset_class, 'Other')

    def _convert_to_usd(self, amount: float, currency: str) -> float:
        """Convert amount to USD (placeholder implementation)"""
        # Placeholder FX rates - in production would use real-time rates
        fx_rates = {
            'USD': 1.0,
            'EUR': 1.1,
            'CHF': 1.1,
            'GBP': 1.25,
            'SEK': 0.095,
            'NOK': 0.09,
            'DKK': 0.15
        }

        rate = fx_rates.get(currency, 1.0)
        return amount * rate

    def get_portfolio_summary(self, positions: List[Dict]) -> Dict:
        """Generate portfolio summary from positions"""
        if not positions:
            return {
                "total_value_usd": 0.0,
                "total_positions": 0,
                "asset_allocation": {},
                "currency_exposure": {},
                "top_holdings": [],
            }

        total_value = sum(p.get("market_value_usd", 0) for p in positions)

        # Asset class allocation
        asset_allocation = {}
        for pos in positions:
            asset_class = pos.get("asset_class", "Other")
            value = pos.get("market_value_usd", 0)
            asset_allocation[asset_class] = asset_allocation.get(asset_class, 0) + value

        # Convert to percentages
        if total_value > 0:
            asset_allocation = {k: (v / total_value) * 100 for k, v in asset_allocation.items()}

        # Currency exposure
        currency_exposure = {}
        for pos in positions:
            currency = pos.get("currency", "USD")
            value = pos.get("market_value_usd", 0)
            currency_exposure[currency] = currency_exposure.get(currency, 0) + value

        if total_value > 0:
            currency_exposure = {k: (v / total_value) * 100 for k, v in currency_exposure.items()}

        return {
            "total_value_usd": total_value,
            "total_positions": len(positions),
            "asset_allocation": asset_allocation,
            "currency_exposure": currency_exposure,
            "top_holdings": sorted(positions, key=lambda x: x.get("market_value_usd", 0), reverse=True)[:10]
        }