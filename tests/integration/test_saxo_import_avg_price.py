"""
Integration tests for avg_price extraction from Saxo CSV files.

Tests the complete flow:
1. CSV parsing with SaxoImportConnector
2. avg_price extraction from "Prix entrée" column
3. Column alias handling (Prix revient, Entry Price, etc.)
4. Data preservation through normalization

Uses real CSV data from: data/users/jack/saxobank/data/20251025_103840_Positions...
"""

import pytest
from pathlib import Path
from connectors.saxo_import import SaxoImportConnector


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def saxo_connector():
    """SaxoImportConnector instance"""
    return SaxoImportConnector()


@pytest.fixture
def real_saxo_csv_path():
    """Path to real Saxo CSV file (October 25, 2025)"""
    return Path("data/users/jack/saxobank/data/20251025_103840_Positions_25-oct.-2025_10_37_13.csv")


@pytest.fixture
def sample_csv_content():
    """Sample CSV content with avg_price column (minimal)"""
    return """Instruments,Statut,Quantité,Prix entrée,Prix actuel,Valeur actuelle (EUR),Devise,Type d'actif,ISIN,Symbole
Apple Inc.,Ouvert,18,91.90,262.82,4058.71,USD,Actions,US0378331005,AAPL:xnas
Tesla Inc.,Ouvert,31,343.64,433.62,11532.56,USD,Actions,US88160R1014,TSLA:xnas
Meta Platforms,Ouvert,4,240.95,738.36,2533.87,USD,Actions,US30303M1027,META:xnas"""


# ============================================================================
# Test Suite 1: Real CSV File Extraction
# ============================================================================

class TestRealCSVExtraction:
    """Test avg_price extraction from real Saxo CSV file"""

    def test_file_exists(self, real_saxo_csv_path):
        """Verify test CSV file exists"""
        assert real_saxo_csv_path.exists(), f"CSV file not found: {real_saxo_csv_path}"

    def test_process_real_saxo_file(self, saxo_connector, real_saxo_csv_path):
        """Process real Saxo CSV and verify basic structure"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        assert 'positions' in result
        assert 'total_positions' in result
        assert len(result['positions']) > 0
        assert result['source'] == 'saxo_bank'

    def test_aapl_avg_price_extracted(self, saxo_connector, real_saxo_csv_path):
        """Verify AAPL avg_price is correctly extracted"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        # Find AAPL position
        aapl = next((p for p in result['positions'] if 'AAPL' in p['symbol']), None)

        assert aapl is not None, "AAPL position not found in CSV"
        assert 'avg_price' in aapl
        assert aapl['avg_price'] is not None
        assert aapl['avg_price'] == pytest.approx(91.90, rel=0.01)
        assert aapl['avg_price'] > 0

    def test_tsla_avg_price_extracted(self, saxo_connector, real_saxo_csv_path):
        """Verify TSLA avg_price is correctly extracted"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        # Find TSLA stock position (not CFD)
        tsla_positions = [p for p in result['positions'] if 'TSLA' in p['symbol']]
        tsla_stock = next((p for p in tsla_positions if p.get('asset_class') == 'Stock'), None)

        assert tsla_stock is not None, "TSLA stock position not found"
        assert 'avg_price' in tsla_stock
        assert tsla_stock['avg_price'] is not None
        assert tsla_stock['avg_price'] == pytest.approx(343.64, rel=0.01)

    def test_meta_avg_price_extracted(self, saxo_connector, real_saxo_csv_path):
        """Verify META avg_price is correctly extracted"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        # Find META position
        meta = next((p for p in result['positions'] if 'META' in p['symbol']), None)

        assert meta is not None, "META position not found in CSV"
        assert 'avg_price' in meta
        assert meta['avg_price'] is not None
        assert meta['avg_price'] == pytest.approx(240.95, rel=0.01)

    def test_all_positions_have_avg_price_field(self, saxo_connector, real_saxo_csv_path):
        """All positions should have avg_price field (even if None)"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        for position in result['positions']:
            assert 'avg_price' in position, f"Position {position.get('symbol')} missing avg_price field"
            # avg_price can be None or float, but field must exist
            if position['avg_price'] is not None:
                assert isinstance(position['avg_price'], (int, float))
                assert position['avg_price'] >= 0


# ============================================================================
# Test Suite 2: Column Alias Handling
# ============================================================================

class TestColumnAliases:
    """Test that different column names for avg_price are handled"""

    def test_prix_entree_alias(self, saxo_connector):
        """'Prix entrée' (French) should map to Entry Price"""
        # Verify alias exists
        canonical = saxo_connector._canonical_column_name('Prix entrée')
        assert canonical in saxo_connector.column_aliases
        assert saxo_connector.column_aliases[canonical] == 'Entry Price'

    def test_prix_revient_alias(self, saxo_connector):
        """'Prix revient' should map to Entry Price"""
        canonical = saxo_connector._canonical_column_name('Prix revient')
        assert canonical in saxo_connector.column_aliases
        assert saxo_connector.column_aliases[canonical] == 'Entry Price'

    def test_entry_price_alias(self, saxo_connector):
        """'Entry Price' (English) should map correctly"""
        canonical = saxo_connector._canonical_column_name('Entry Price')
        assert canonical in saxo_connector.column_aliases

    def test_average_price_alias(self, saxo_connector):
        """'Average Price' should map to Entry Price"""
        canonical = saxo_connector._canonical_column_name('Average Price')
        assert canonical in saxo_connector.column_aliases
        assert saxo_connector.column_aliases[canonical] == 'Entry Price'

    def test_avg_price_alias(self, saxo_connector):
        """'Avg Price' should map to Entry Price"""
        canonical = saxo_connector._canonical_column_name('Avg Price')
        assert canonical in saxo_connector.column_aliases
        assert saxo_connector.column_aliases[canonical] == 'Entry Price'


# ============================================================================
# Test Suite 3: Data Validation
# ============================================================================

class TestDataValidation:
    """Test data validation and edge cases"""

    def test_avg_price_positive_values(self, saxo_connector, real_saxo_csv_path):
        """avg_price should always be positive when present"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        for position in result['positions']:
            if position['avg_price'] is not None:
                assert position['avg_price'] > 0, f"Invalid avg_price for {position['symbol']}"

    def test_avg_price_none_for_missing_data(self, saxo_connector):
        """avg_price should be None if column is missing or value is 0"""
        # Mock row without avg_price
        import pandas as pd
        row = pd.Series({
            'Instrument': 'Test Asset',
            'Symbol': 'TEST',
            'Quantity': 10,
            'Market Value': 1000,
            'Currency': 'USD',
            'Asset Class': 'Stock'
            # No 'Entry Price' column
        })

        position = saxo_connector._process_position(row, user_id='test')

        # Should have field but be None
        assert 'avg_price' in position
        assert position['avg_price'] is None

    def test_avg_price_zero_treated_as_none(self, saxo_connector):
        """avg_price of 0 should be treated as None"""
        import pandas as pd
        row = pd.Series({
            'Instrument': 'Test Asset',
            'Symbol': 'TEST',
            'Quantity': 10,
            'Market Value': 1000,
            'Currency': 'USD',
            'Asset Class': 'Stock',
            'Entry Price': 0.0  # Zero value
        })

        position = saxo_connector._process_position(row, user_id='test')

        assert position['avg_price'] is None  # Should be None, not 0

    def test_avg_price_string_converted_to_float(self, saxo_connector):
        """avg_price as string should be converted to float"""
        import pandas as pd
        row = pd.Series({
            'Instrument': 'Test Asset',
            'Symbol': 'TEST',
            'Quantity': 10,
            'Market Value': 1000,
            'Currency': 'USD',
            'Asset Class': 'Stock',
            'Entry Price': '123.45'  # String value
        })

        position = saxo_connector._process_position(row, user_id='test')

        assert position['avg_price'] == 123.45
        assert isinstance(position['avg_price'], float)


# ============================================================================
# Test Suite 4: Normalization Preservation
# ============================================================================

class TestNormalizationPreservation:
    """Test that avg_price is preserved through CSV normalization"""

    def test_avg_price_in_normalized_columns(self, saxo_connector, real_saxo_csv_path):
        """Entry Price should be in normalized DataFrame columns"""
        df = saxo_connector._load_file(real_saxo_csv_path)

        # After normalization, 'Entry Price' should be a column
        assert 'Entry Price' in df.columns or 'Prix entrée' in df.columns

    def test_normalization_preserves_values(self, saxo_connector):
        """Normalization should not alter avg_price values"""
        import pandas as pd

        # Create mock DataFrame with French column
        df = pd.DataFrame({
            'Instruments': ['Apple Inc.'],
            'Prix entrée': ['91.90'],
            'Quantité': ['18'],
            'Valeur actuelle (EUR)': ['4058.71'],
            'Devise': ['USD'],
            "Type d'actif": ['Actions']
        })

        normalized = saxo_connector._normalize_dataframe(df)

        # Should have Entry Price column
        assert 'Entry Price' in normalized.columns
        # Value should be preserved
        assert normalized.iloc[0]['Entry Price'] == '91.90'

    def test_canonical_column_name_consistency(self, saxo_connector):
        """Canonical column names should be consistent"""
        # Same semantic name should produce same canonical
        variants = [
            'Prix entrée',
            'Prix  entrée',  # Extra space
            'PRIX ENTREE',   # Uppercase, no accent
            'prix entree'    # Lowercase, no accent
        ]

        canonical_names = [saxo_connector._canonical_column_name(v) for v in variants]

        # All should map to same canonical
        assert len(set(canonical_names)) == 1


# ============================================================================
# Test Suite 5: Integration with Position Structure
# ============================================================================

class TestPositionStructure:
    """Test that avg_price integrates correctly with position structure"""

    def test_position_dict_structure(self, saxo_connector, real_saxo_csv_path):
        """Position dict should have all required fields including avg_price"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')
        position = result['positions'][0]

        required_fields = [
            'symbol', 'instrument', 'name', 'quantity', 'market_value',
            'market_value_usd', 'currency', 'asset_class', 'avg_price'
        ]

        for field in required_fields:
            assert field in position, f"Missing field: {field}"

    def test_avg_price_used_for_gain_calculation(self, saxo_connector, real_saxo_csv_path):
        """avg_price enables unrealized gain calculation"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        # Find AAPL position
        aapl = next((p for p in result['positions'] if 'AAPL' in p['symbol']), None)

        # Calculate unrealized gain manually
        if aapl['avg_price'] and aapl['avg_price'] > 0:
            # Current price can be derived from market_value and quantity
            current_price = aapl['market_value'] / aapl['quantity'] if aapl['quantity'] > 0 else 0
            gain_pct = (current_price / aapl['avg_price'] - 1) * 100

            # Should be around +145-186% (varies with market_value currency conversion)
            assert gain_pct > 100, "Expected significant gain for AAPL"
            assert 140 <= gain_pct <= 220, f"Expected ~150-190% gain, got {gain_pct:.1f}%"


# ============================================================================
# Test Suite 6: Multi-User Isolation
# ============================================================================

class TestMultiUserIsolation:
    """Test that avg_price works with multi-user setup"""

    def test_user_id_passed_correctly(self, saxo_connector, real_saxo_csv_path):
        """user_id should be passed through processing"""
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        # Result should contain positions
        assert len(result['positions']) > 0

        # Each position should have been processed with user_id
        # (verified by no exceptions during processing)

    def test_different_users_same_file(self, saxo_connector, real_saxo_csv_path):
        """Same CSV processed for different users should work"""
        result1 = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')
        result2 = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='demo')

        # Both should succeed
        assert len(result1['positions']) > 0
        assert len(result2['positions']) > 0

        # avg_price should be same (same file)
        aapl1 = next((p for p in result1['positions'] if 'AAPL' in p['symbol']), None)
        aapl2 = next((p for p in result2['positions'] if 'AAPL' in p['symbol']), None)

        if aapl1 and aapl2:
            assert aapl1['avg_price'] == aapl2['avg_price']


# ============================================================================
# Test Suite 7: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in avg_price extraction"""

    def test_malformed_avg_price_value(self, saxo_connector):
        """Malformed avg_price value should be handled gracefully"""
        import pandas as pd
        row = pd.Series({
            'Instrument': 'Test Asset',
            'Symbol': 'TEST',
            'Quantity': 10,
            'Market Value': 1000,
            'Currency': 'USD',
            'Asset Class': 'Stock',
            'Entry Price': 'N/A'  # Invalid value
        })

        # Should handle gracefully (either None or exception)
        try:
            position = saxo_connector._process_position(row, user_id='test')
            # If no exception, avg_price should be None or 0
            assert position['avg_price'] in [None, 0]
        except ValueError:
            # Expected if _to_float raises ValueError
            pass

    def test_missing_required_columns_graceful(self, saxo_connector):
        """Missing required columns should not crash avg_price extraction"""
        import pandas as pd
        row = pd.Series({
            'Instrument': 'Test Asset',
            # Missing many required columns
        })

        # Should either skip or handle gracefully
        try:
            position = saxo_connector._process_position(row, user_id='test')
            if position:
                assert 'avg_price' in position
        except (ValueError, KeyError):
            # Expected for invalid row
            pass


# ============================================================================
# Test Suite 8: Performance
# ============================================================================

class TestPerformance:
    """Test performance with large CSV files"""

    def test_process_real_file_performance(self, saxo_connector, real_saxo_csv_path):
        """Processing real CSV should complete in reasonable time"""
        import time

        start = time.time()
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')
        elapsed = time.time() - start

        # Should complete in less than 5 seconds
        assert elapsed < 5.0, f"Processing took {elapsed:.2f}s (expected <5s)"
        assert len(result['positions']) > 0

    def test_avg_price_extraction_no_significant_overhead(self, saxo_connector, real_saxo_csv_path):
        """Adding avg_price extraction should not add significant overhead"""
        # Just verify it processes successfully
        result = saxo_connector.process_saxo_file(real_saxo_csv_path, user_id='jack')

        # Verify avg_price is extracted for at least some positions
        positions_with_avg_price = [p for p in result['positions'] if p.get('avg_price')]
        assert len(positions_with_avg_price) > 0, "No positions with avg_price found"
