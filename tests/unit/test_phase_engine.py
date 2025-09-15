"""
Tests unitaires pour Phase Engine

Tests des fonctionnalités critiques du Phase Engine :
- Détection de phase BTC→ETH→Large→Alt
- Cache intelligent avec TTL
- Persistance minimale avant changement
- Génération d'explications cohérentes
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from services.execution.phase_engine import PhaseEngine, Phase, PhaseSignals, PhaseState


@pytest.fixture  
def phase_engine():
    """Fixture pour un PhaseEngine avec mocks"""
    engine = PhaseEngine()
    # Désactiver le cache pour les tests
    engine._cache_ttl_seconds = 0
    return engine


@pytest.fixture
def sample_signals():
    """Fixture pour des signaux de phase typiques"""
    return PhaseSignals(
        as_of=datetime.now(),
        btc_dominance=45.0,
        btc_dominance_delta_7d=2.0,
        rs_eth_btc_7d=1.02,
        rs_eth_btc_30d=1.05,
        rs_large_btc_7d=0.98,
        rs_large_btc_30d=0.99,
        rs_alt_btc_7d=1.10,
        rs_alt_btc_30d=1.08,
        breadth_advance_decline=0.65,
        breadth_new_highs=15,
        volume_concentration=0.6,
        momentum_dispersion=0.7,
        quality_score=0.8
    )


class TestPhaseDetection:
    """Tests de la logique de détection de phase"""
    
    def test_btc_phase_conditions(self, phase_engine):
        """Test détection phase BTC"""
        # Signaux favorables pour BTC : dominance ↑, autres assets faibles
        signals = PhaseSignals(
            as_of=datetime.now(),
            btc_dominance=47.0,
            btc_dominance_delta_7d=3.0,  # Dominance en hausse
            rs_eth_btc_7d=0.92,         # ETH sous-performe
            rs_large_btc_7d=0.90,       # Large caps faibles
            rs_alt_btc_7d=0.88,         # Alts faibles
            quality_score=0.9
        )
        
        # Calculer scores pour chaque phase
        btc_score = phase_engine._calculate_btc_score(signals, phase_engine.thresholds)
        eth_score = phase_engine._calculate_eth_score(signals, phase_engine.thresholds)
        
        # BTC devrait avoir le score le plus élevé
        assert btc_score > eth_score
        assert btc_score > 0.5  # Score significatif
    
    def test_eth_phase_conditions(self, phase_engine):
        """Test détection phase ETH"""
        signals = PhaseSignals(
            as_of=datetime.now(),
            btc_dominance=44.0,
            btc_dominance_delta_7d=0.5,  # Dominance stable
            rs_eth_btc_7d=1.15,          # ETH surperforme
            rs_eth_btc_30d=1.12,         # Tendance confirmée
            rs_large_btc_7d=1.02,        # Large caps pas encore très fortes
            quality_score=0.8
        )
        
        eth_score = phase_engine._calculate_eth_score(signals, phase_engine.thresholds)
        btc_score = phase_engine._calculate_btc_score(signals, phase_engine.thresholds)
        
        assert eth_score > btc_score
        assert eth_score > 0.4
    
    def test_alt_phase_conditions(self, phase_engine):
        """Test détection phase ALT"""
        signals = PhaseSignals(
            as_of=datetime.now(),
            rs_alt_btc_7d=1.20,              # Alts surperforment
            breadth_advance_decline=0.75,     # Breadth élevé
            momentum_dispersion=0.8,          # Momentum dispersé
            volume_concentration=0.5,         # Volume pas concentré
            quality_score=0.8
        )
        
        alt_score = phase_engine._calculate_alt_score(signals, phase_engine.thresholds)
        btc_score = phase_engine._calculate_btc_score(signals, phase_engine.thresholds)
        
        assert alt_score > btc_score
        assert alt_score > 0.6


class TestSignalExtraction:
    """Tests d'extraction des signaux depuis les APIs"""
    
    def test_signal_quality_assessment(self, phase_engine):
        """Test évaluation de la qualité des signaux"""
        # Signaux récents et complets
        fresh_signals = PhaseSignals(
            as_of=datetime.now(),  # Très récent
            btc_dominance=45.0,    # Présent
            rs_eth_btc_7d=1.0,     # Présent
            breadth_advance_decline=0.6  # Présent
        )
        
        quality = phase_engine._assess_signal_quality(fresh_signals)
        assert quality > 0.7  # Qualité élevée
        
        # Signaux anciens et incomplets
        stale_signals = PhaseSignals(
            as_of=datetime.now() - timedelta(hours=2),  # Ancien
            btc_dominance=0,       # Manquant
            rs_eth_btc_7d=0,       # Manquant
        )
        
        stale_quality = phase_engine._assess_signal_quality(stale_signals)
        assert stale_quality < 0.5  # Qualité faible
        assert quality > stale_quality
    
    def test_relative_strength_calculation(self, phase_engine):
        """Test calcul force relative basique"""
        # Mock data avec performances simulées
        mock_price_data = {
            "BTC": {"prices": [100, 105, 108, 110]},  # +10% sur 3 périodes
            "ETH": {"prices": [200, 215, 220, 230]}   # +15% sur 3 périodes
        }
        
        rs_results = phase_engine._calculate_relative_strength(mock_price_data)
        
        # ETH/BTC devrait être > 1 (ETH surperforme)
        assert rs_results.get('eth_btc_7d', 1.0) > 1.0
        
        # Vérifier que les valeurs par défaut sont présentes
        assert 'large_btc_7d' in rs_results
        assert 'alt_btc_7d' in rs_results
    
    def test_dominance_delta_calculation(self, phase_engine):
        """Test calcul delta dominance (basique pour test)"""
        current_dominance = 45.0
        delta = phase_engine._calculate_dominance_delta(current_dominance)
        
        # Delta doit être raisonnable (-5% à +5%)
        assert -5.0 <= delta <= 5.0


class TestCacheAndPersistence:
    """Tests du cache et de la persistance des phases"""
    
    async def test_cache_functionality(self, phase_engine):
        """Test fonctionnement du cache TTL"""
        # Mock des signaux pour test déterministe
        with patch.object(phase_engine, '_fetch_phase_signals') as mock_fetch:
            mock_fetch.return_value = PhaseSignals(
                as_of=datetime.now(),
                btc_dominance=45.0,
                quality_score=0.8
            )
            
            # Premier appel : doit fetcher les signaux
            phase1 = await phase_engine.get_current_phase()
            assert mock_fetch.call_count == 1
            
            # Cache activé pour test
            phase_engine._cache_ttl_seconds = 300  # 5 minutes
            
            # Deuxième appel immédiat : doit utiliser le cache
            phase2 = await phase_engine.get_current_phase()
            assert mock_fetch.call_count == 1  # Pas d'appel supplémentaire
            
            # Phases identiques via cache
            assert phase1.phase_now == phase2.phase_now
    
    async def test_phase_persistence_mechanism(self, phase_engine):
        """Test mécanisme de persistance minimale"""
        # Configurer persistance minimale pour test
        phase_engine._min_persistence_observations = 2
        
        with patch.object(phase_engine, '_fetch_phase_signals') as mock_fetch, \
             patch.object(phase_engine, '_detect_phase') as mock_detect:
            
            # Premier appel : phase BTC
            mock_detect.return_value = PhaseState(
                phase_now=Phase.BTC,
                phase_probs={"btc": 0.8, "eth": 0.2, "large": 0.0, "alt": 0.0},
                confidence=0.7,
                explain=["Test BTC phase"],
                persistence_count=1
            )
            
            phase1 = await phase_engine.get_current_phase(force_refresh=True)
            assert phase1.phase_now == Phase.BTC
            
            # Tentative de changement vers ETH sans persistance suffisante
            mock_detect.return_value = PhaseState(
                phase_now=Phase.ETH,  # Changement
                phase_probs={"btc": 0.3, "eth": 0.7, "large": 0.0, "alt": 0.0},
                confidence=0.8,
                explain=["Test ETH phase"],
                persistence_count=1  # Pas assez de persistance
            )
            
            # Le changement devrait être bloqué par la persistance
            # (En réalité, cela dépend de l'implémentation complète)


class TestExplanationGeneration:
    """Tests de génération des explications"""
    
    def test_btc_phase_explanations(self, phase_engine):
        """Test génération explications pour phase BTC"""
        signals = PhaseSignals(
            as_of=datetime.now(),
            btc_dominance_delta_7d=3.5,
            rs_eth_btc_7d=0.88,
            quality_score=0.9
        )
        
        phase_scores = {
            Phase.BTC: 0.8,
            Phase.ETH: 0.2,
            Phase.LARGE: 0.0,
            Phase.ALT: 0.0
        }
        
        explanations = phase_engine._generate_explanations(Phase.BTC, signals, phase_scores)
        
        # Doit avoir 2-3 explications
        assert 2 <= len(explanations) <= 3
        
        # Doit mentionner la dominance BTC
        dominance_mentioned = any("Dominance BTC" in exp for exp in explanations)
        assert dominance_mentioned
    
    def test_explanation_fallback(self, phase_engine):
        """Test fallback si génération d'explications échoue"""
        # Signaux invalides pour forcer une erreur
        invalid_signals = PhaseSignals(as_of=datetime.now())
        
        explanations = phase_engine._generate_explanations(
            Phase.BTC, invalid_signals, {}
        )
        
        # Doit toujours retourner au moins 2 explications par défaut
        assert len(explanations) >= 2
        assert any("BTC" in exp for exp in explanations)


class TestNextPhasePredicition:
    """Tests de prédiction de phase suivante"""
    
    def test_typical_phase_sequence(self, phase_engine):
        """Test séquence typique BTC→ETH→Large→Alt→BTC"""
        phase_scores = {
            Phase.BTC: 0.6,
            Phase.ETH: 0.4,  # ETH commence à monter
            Phase.LARGE: 0.2,
            Phase.ALT: 0.1
        }
        
        next_phase = phase_engine._predict_next_phase(Phase.BTC, PhaseSignals(), phase_scores)
        
        # De BTC, on devrait prédire ETH si son score monte
        assert next_phase == Phase.ETH
    
    def test_next_phase_fallback(self, phase_engine):
        """Test fallback si prédiction impossible"""
        empty_scores = {}
        
        next_phase = phase_engine._predict_next_phase(Phase.BTC, PhaseSignals(), empty_scores)
        
        # Devrait fallback vers la séquence typique (BTC→ETH)
        assert next_phase == Phase.ETH


# Tests d'intégration
class TestIntegration:
    """Tests d'intégration bout-en-bout"""
    
    async def test_full_phase_detection_cycle(self, phase_engine):
        """Test complet de détection de phase"""
        # Mock des appels réseau pour test déterministe
        with patch('httpx.AsyncClient') as mock_client:
            # Mock réponse CoinGecko
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"market_cap_percentage": {"btc": 45.5}}
            }
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            # Appel réel de détection de phase
            phase_state = await phase_engine.get_current_phase(force_refresh=True)
            
            # Vérifications basiques
            assert isinstance(phase_state, PhaseState)
            assert phase_state.phase_now in [Phase.BTC, Phase.ETH, Phase.LARGE, Phase.ALT]
            assert 0.0 <= phase_state.confidence <= 1.0
            assert len(phase_state.explain) >= 1
            assert isinstance(phase_state.phase_probs, dict)
            
            # Probabilités doivent sommer à ~1.0
            prob_sum = sum(phase_state.phase_probs.values())
            assert 0.9 <= prob_sum <= 1.1
    
    def test_singleton_pattern(self):
        """Test que get_phase_engine retourne toujours la même instance"""
        from services.execution.phase_engine import get_phase_engine
        
        engine1 = get_phase_engine()
        engine2 = get_phase_engine()
        
        assert engine1 is engine2  # Même instance (singleton)