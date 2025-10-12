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
            'val actuelle': 'Market Value',
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
            'isin': 'ISIN',
            'statut': 'Status',
            'etat': 'Status',
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
            # Use csv module for robust handling of newlines in quoted fields
            import csv
            for encoding in ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252']:
                for sep in [',', ';', '\t']:
                    try:
                        rows = []
                        with open(file_path, 'r', encoding=encoding, newline='') as f:
                            reader = csv.DictReader(f, delimiter=sep)
                            for row in reader:
                                # Clean newlines in all values
                                cleaned_row = {k: str(v).replace('\n', ' ').replace('\r', ' ').strip() if v else v
                                              for k, v in row.items()}
                                rows.append(cleaned_row)

                        if rows and len(rows[0].keys()) > 1:  # Valid CSV should have multiple columns
                            df = pd.DataFrame(rows)
                            return self._normalize_dataframe(df)
                    except:
                        continue
            raise ValueError("Could not read CSV file with any common encoding/separator")
        else:
            df = pd.read_excel(file_path)
            return self._normalize_dataframe(df)

    def process_saxo_file(self, file_path: Union[str, Path], user_id: Optional[str] = None) -> Dict[str, Union[List, Dict, str]]:
        """
        Process Saxo Bank export file and return standardized data

        Args:
            file_path: Path to Saxo CSV/XLSX file
            user_id: Optional user ID for per-user catalog enrichment

        Returns:
            Dict with processed positions and metadata
        """
        try:
            df = self._load_file(Path(file_path))
            logger.info(f"Processing Saxo file with {len(df)} positions for user {user_id or 'global'}")
            logger.debug(f"Columns after normalization: {list(df.columns)[:10]}")

            # Debug: afficher premières lignes
            if len(df) > 0:
                logger.debug(f"First row Instrument column: {df.iloc[0].get('Instrument')}")
                logger.debug(f"First row Status column: {df.iloc[0].get('Status')}")
                logger.debug(f"First row Quantity column: {df.iloc[0].get('Quantity')}")

            # Clean and standardize data
            positions = []
            errors = []

            for idx, row in df.iterrows():
                try:
                    position = self._process_position(row, user_id=user_id)
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

    def _process_position(self, row: pd.Series, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        Process a single position row with enrichment via instruments registry.

        Args:
            row: DataFrame row with position data
            user_id: Optional user ID for per-user catalog lookup

        Returns:
            Enriched position dict or None if invalid
        """
        try:
            # Clean all string values (remove newlines, extra spaces)
            def clean_str(val):
                if pd.isna(val):
                    return ''
                return str(val).replace('\n', ' ').replace('\r', ' ').strip()

            position_id = clean_str(row.get('Position ID', ''))
            instrument_raw = clean_str(row.get('Instrument', ''))
            symbol_raw = clean_str(row.get('Symbol', ''))
            isin_raw = clean_str(row.get('ISIN', ''))
            status = clean_str(row.get('Status', ''))
            quantity = self._to_float(row.get('Quantity', 0))
            market_value = self._to_float(row.get('Market Value', 0))
            currency = clean_str(row.get('Currency', 'USD')).upper() or 'USD'
            asset_class_raw = clean_str(row.get('Asset Class', 'Unknown')) or 'Unknown'

            # Skip summary rows (e.g., "Actions (95)")
            if instrument_raw and ('(' in instrument_raw and ')' in instrument_raw and instrument_raw.split('(')[0].strip().lower() in ['actions', 'obligations', 'etf', 'etfs']):
                logger.debug(f"Skipping summary row: {instrument_raw}")
                return None

            # Skip rows with "Ouvert" as instrument (status leaked into instrument column)
            if instrument_raw.lower() in ['ouvert', 'ferme', 'clos', 'open', 'closed']:
                logger.debug(f"Skipping status row: {instrument_raw}")
                return None

            # Must have valid instrument name and quantity
            if not instrument_raw or quantity == 0:
                return None

            # Use Symbol column if available, otherwise extract from instrument
            symbol = symbol_raw if symbol_raw else self._standardize_symbol(instrument_raw)

            # Clean symbol (remove exchange suffix like :xnas)
            if ':' in symbol:
                symbol = symbol.split(':')[0].strip()

            market_value_usd = self._convert_to_usd(market_value, currency)

            # Enrichissement via registry (nom lisible, exchange, etc.)
            # Priority: ISIN > Symbol > Instrument name
            lookup_key = isin_raw if isin_raw else (symbol if symbol else instrument_raw)

            from services.instruments_registry import resolve
            enriched = resolve(lookup_key, fallback_symbol=symbol, user_id=user_id)

            # Use original instrument name if registry doesn't have a better name
            display_name = instrument_raw  # Always use the nice name from CSV
            enriched_symbol = symbol or enriched.get("symbol") or instrument_raw
            enriched_isin = isin_raw or enriched.get("isin")
            enriched_currency = currency
            enriched_asset_class = self._standardize_asset_class(asset_class_raw)

            logger.debug(f"Processed: {instrument_raw} → symbol={enriched_symbol}, isin={enriched_isin}")

            return {
                "position_id": position_id or enriched_symbol,
                "symbol": enriched_symbol,
                "instrument": instrument_raw,  # Keep original nice name
                "name": display_name,  # Keep original nice name
                "quantity": quantity,
                "market_value": market_value,
                "market_value_usd": market_value_usd,
                "currency": enriched_currency,
                "asset_class": enriched_asset_class,
                "exchange": enriched.get("exchange"),
                "isin": enriched_isin,
                "source": "saxo_bank",
                "import_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing position row: {e}")
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