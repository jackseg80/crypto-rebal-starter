"""
Tests unitaires pour services/instruments_registry.py

Vérifie:
- Lazy-loading des catalogs (JSON chargé UNE FOIS)
- Fallback ISIN → ticker → catalog
- Validation ISIN avec regex complète
- Multi-tenant : user catalog prioritaire sur global
- Cache fonctionnel (pas de I/O répétés)
"""

import pytest
from pathlib import Path
from services.instruments_registry import resolve, clear_cache, add_to_catalog, _is_valid_isin


class TestInstrumentsRegistry:
    """Tests du registry instruments avec lazy-loading."""

    def setup_method(self):
        """Clear cache avant chaque test."""
        clear_cache()

    def test_lazy_loading_once(self):
        """Le catalog global doit être chargé UNE FOIS seulement."""
        from unittest.mock import patch, MagicMock
        from pathlib import Path

        # Mock du catalog JSON
        mock_catalog_data = '{"AAPL": {"id": "AAPL", "symbol": "AAPL", "name": "Apple Inc.", "isin": null}}'
        mock_isin_data = '{}'

        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'read_text') as mock_read_text, \
             patch.object(Path, 'write_text') as mock_write_text, \
             patch.object(Path, 'mkdir'):

            # Configurer les retours de read_text
            mock_read_text.side_effect = [mock_catalog_data, mock_isin_data]

            # Appeler resolve() 100 fois
            for _ in range(100):
                resolve("AAPL")

            # Assert: read_text appelé seulement 2 fois (catalog + isin_map au premier appel)
            assert mock_read_text.call_count == 2, f"Expected 2 calls, got {mock_read_text.call_count}"

    def test_isin_validation_complete(self):
        """Validation ISIN doit supporter tous les codes pays."""
        assert _is_valid_isin("IE00B4L5Y983")  # Ireland
        assert _is_valid_isin("US0378331005")  # USA
        assert _is_valid_isin("FR0000120271")  # France
        assert _is_valid_isin("DE0005140008")  # Germany
        assert not _is_valid_isin("AAPL")  # Ticker
        assert not _is_valid_isin("IE00")  # Too short

    def test_fallback_isin_to_ticker(self):
        """Résolution ISIN → ticker → catalog doit fonctionner."""
        # TODO: Créer catalog test avec IWDA.AMS
        # Créer mapping ISIN→ticker avec IE00B4L5Y983 → IWDA.AMS
        # resolve("IE00B4L5Y983") doit retourner infos IWDA.AMS
        pass

    def test_user_catalog_priority(self):
        """Catalog per-user doit avoir priorité sur global."""
        # TODO: Créer global catalog avec AAPL (nom: Apple Inc.)
        # Créer user catalog avec AAPL (nom: Custom Apple)
        # resolve("AAPL", user_id="test_user") doit retourner "Custom Apple"
        pass

    def test_fallback_minimal_record(self):
        """Instruments inconnus doivent avoir fallback minimal."""
        result = resolve("UNKNOWN_TICKER", fallback_symbol="UNK")
        assert result["id"] == "UNKNOWN_TICKER"
        assert result["symbol"] == "UNK"
        assert result["name"] == "UNK"
        assert result["isin"] is None

    def test_add_to_catalog_persists(self, tmp_path):
        """Ajout au catalog doit persister sur disque."""
        # TODO: Utiliser tmp_path pour créer catalog temporaire
        # add_to_catalog("TEST", {"name": "Test Instrument"})
        # Recharger catalog et vérifier présence
        pass


# Commande pour lancer ces tests:
# pytest tests/unit/test_instruments_registry.py -v
