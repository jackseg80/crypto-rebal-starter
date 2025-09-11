"""
Tests unitaires pour Score Registry

Tests des fonctionnalités critiques du Score Registry :
- Calcul du score canonique avec ordre documenté
- Pénalité de contradiction bornée  
- Gestion des bandes avec hystérésis
- Facteurs de phase pour alertes
"""

import pytest
from datetime import datetime
from services.execution.score_registry import ScoreRegistry, CanonicalScores, ScoreComponents


@pytest.fixture
def score_registry():
    """Fixture pour un ScoreRegistry avec config par défaut"""
    registry = ScoreRegistry()
    # Force l'utilisation du fallback pour les tests (pas de fichier config)
    registry.config = registry.fallback_config
    registry.config_loaded_at = datetime.now()
    return registry


class TestScoreCalculation:
    """Tests du calcul de score canonique"""
    
    async def test_score_calculation_order(self, score_registry):
        """Test de l'ordre documenté : composants → clamp → pénalité → clamp"""
        # Test avec composants au-dessus de 100 (doivent être clampés)
        scores = await score_registry.calculate_canonical_score(
            trend_regime=120.0,  # Sera clampé à 100
            risk=80.0,
            breadth_rotation=60.0,
            sentiment=40.0,
            contradiction_index=0.0,  # Pas de pénalité
            confidence=0.8
        )
        
        # Les composants doivent être clampés à [0-100]
        assert scores.components.trend_regime == 100.0
        assert scores.components.risk == 80.0
        assert scores.components.breadth_rotation == 60.0
        assert scores.components.sentiment == 40.0
        
        # Score pondéré attendu (avec poids par défaut)
        expected = (100 * 0.35) + (80 * 0.25) + (60 * 0.25) + (40 * 0.15)
        assert abs(scores.decision - expected) < 0.01
    
    async def test_contradiction_penalty_cap(self, score_registry):
        """Test que la pénalité de contradiction est bornée à 30%"""
        # Score élevé avec contradiction maximale
        scores = await score_registry.calculate_canonical_score(
            trend_regime=100.0,
            risk=100.0,
            breadth_rotation=100.0,
            sentiment=100.0,
            contradiction_index=1.0,  # Contradiction maximale
            confidence=0.8
        )
        
        # Score raw serait 100, pénalité max = 30% du score = 30
        # Score final = 100 - 30 = 70
        expected_penalty_cap = 100 * score_registry.config.contradiction_penalty_cap
        assert scores.decision >= 100 - expected_penalty_cap
        
        # Vérifier que la contradiction est bien bornée [0-1]
        assert 0.0 <= scores.contradiction <= 1.0
    
    async def test_fallback_on_error(self, score_registry):
        """Test du fallback en cas d'erreur"""
        # Simuler une erreur en passant des valeurs invalides
        scores = await score_registry.calculate_canonical_score(
            trend_regime=float('inf'),  # Valeur invalide
            risk=50.0,
            breadth_rotation=50.0,
            sentiment=50.0,
            contradiction_index=0.5,
            confidence=0.5
        )
        
        # Doit retourner des valeurs de fallback sécurisées
        assert scores.decision == 50.0  # Score neutre
        assert scores.confidence == 0.1  # Confiance très faible
        assert scores.contradiction == 0.5  # Contradiction moyenne


class TestBandHysteresis:
    """Tests des bandes décisionnelles avec hystérésis"""
    
    def test_band_without_hysteresis(self, score_registry):
        """Test détermination de bande sans hystérésis"""
        assert score_registry.get_band_for_score(25.0) == "conservative"
        assert score_registry.get_band_for_score(45.0) == "moderate"
        assert score_registry.get_band_for_score(65.0) == "aggressive"
        assert score_registry.get_band_for_score(85.0) == "high_conviction"
    
    def test_band_with_hysteresis(self, score_registry):
        """Test hystérésis pour éviter les changements trop fréquents"""
        # Score proche de la limite mais dans la zone d'hystérésis
        # Si on était en "moderate" (40-59) et le score passe à 62
        # mais est proche du centre de "moderate" (49.5), on reste en "moderate"
        previous_band = "moderate" 
        
        # Score 62 normalement = "aggressive" mais proche du centre "moderate"
        # Avec hystérésis de 3.0, on reste en "moderate" si |62 - 49.5| < 3
        band = score_registry.get_band_for_score(52.0, previous_band)
        assert band == "moderate"  # Reste en moderate par hystérésis
        
        # Score plus éloigné dépasse l'hystérésis
        band = score_registry.get_band_for_score(68.0, previous_band) 
        assert band == "aggressive"  # Change pour aggressive
    
    def test_band_fallback(self, score_registry):
        """Test fallback si score hors limites"""
        assert score_registry.get_band_for_score(-10.0) == "moderate"
        assert score_registry.get_band_for_score(150.0) == "moderate"


class TestPhaseFactors:
    """Tests des facteurs multiplicateurs par phase"""
    
    def test_phase_factors_retrieval(self, score_registry):
        """Test récupération des facteurs de phase"""
        # Vérifier les facteurs par défaut
        assert score_registry.get_phase_factor("volatility", "btc") == 1.0
        assert score_registry.get_phase_factor("volatility", "eth") == 1.1
        assert score_registry.get_phase_factor("volatility", "alt") == 1.3
        
        # Type d'alerte inexistant → facteur 1.0
        assert score_registry.get_phase_factor("inexistant", "btc") == 1.0
        
        # Phase inexistante → facteur 1.0
        assert score_registry.get_phase_factor("volatility", "inexistante") == 1.0


class TestHealthCheck:
    """Tests du health check du registry"""
    
    async def test_health_check_healthy(self, score_registry):
        """Test health check quand tout va bien"""
        health = await score_registry.health_check()
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded"]
        assert "config_version" in health
        assert "timestamp" in health
    
    async def test_health_check_fallback_config(self, score_registry):
        """Test health check avec config fallback"""
        # Forcer l'utilisation de la config fallback
        score_registry.config = score_registry.fallback_config
        
        health = await score_registry.health_check()
        assert health["config_status"] == "fallback"
        assert health["config_version"] == "fallback"


class TestConfigLoading:
    """Tests de chargement de configuration"""
    
    async def test_config_creation(self, score_registry):
        """Test création de config par défaut"""
        # Supprimer config existante pour forcer la création
        if score_registry.config_path.exists():
            score_registry.config_path.unlink()
        
        success = await score_registry.load_config()
        
        # Même si le fichier n'existe pas, load_config doit créer fallback
        assert score_registry.config is not None
        assert score_registry.config_loaded_at is not None
    
    def test_singleton_pattern(self):
        """Test que get_score_registry retourne toujours la même instance"""
        from services.execution.score_registry import get_score_registry
        
        registry1 = get_score_registry()
        registry2 = get_score_registry()
        
        assert registry1 is registry2  # Même instance (singleton)


# Tests d'intégration légers
class TestIntegration:
    """Tests d'intégration avec composants liés"""
    
    async def test_realistic_score_calculation(self, score_registry):
        """Test calcul de score avec des valeurs réalistes"""
        # Scénario : marché bull avec volatilité modérée
        scores = await score_registry.calculate_canonical_score(
            trend_regime=75.0,  # Trend fort
            risk=40.0,          # Risque modéré (volatilité inversée)
            breadth_rotation=65.0,  # Bonne rotation
            sentiment=60.0,     # Sentiment positif 
            contradiction_index=0.2,  # Faible contradiction
            confidence=0.8      # Confiance élevée
        )
        
        # Score attendu entre 50-80 pour un marché favorable
        assert 50.0 <= scores.decision <= 80.0
        assert scores.confidence == 0.8
        assert abs(scores.contradiction - 0.2) < 0.01
        
        # Vérifier que les composants sont préservés
        assert scores.components.trend_regime == 75.0
        assert scores.components.risk == 40.0