"""
Tests unitaires pour Strategy Registry

Tests des fonctionnalités critiques du Strategy Registry :
- Calcul de stratégies selon templates
- Génération d'allocations par phase  
- Poids configurables et normalisation
- Cache intelligent et fallbacks
"""

import pytest
import json
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from services.execution.strategy_registry import (
    StrategyRegistry, StrategyTemplate, StrategyWeights, 
    AllocationTarget, StrategyConfig, get_strategy_registry
)
from services.execution.phase_engine import Phase, PhaseState
from services.execution.score_registry import CanonicalScores, ScoreComponents


@pytest.fixture
def temp_config_path(tmp_path):
    """Fixture pour chemin temporaire de config"""
    return tmp_path / "test_strategy_templates.json"


@pytest.fixture  
def strategy_registry(temp_config_path):
    """Fixture pour StrategyRegistry avec config temporaire"""
    registry = StrategyRegistry(config_path=temp_config_path)
    return registry


@pytest.fixture
def mock_scores():
    """Fixture pour scores canoniques de test"""
    return CanonicalScores(
        decision=65.0,
        confidence=0.8,
        contradiction=0.2,
        components=ScoreComponents(
            trend_regime=70.0,
            risk=40.0,
            breadth_rotation=60.0,
            sentiment=55.0
        ),
        as_of=datetime.now()
    )


@pytest.fixture
def mock_phase_state():
    """Fixture pour état de phase de test"""
    return PhaseState(
        phase_now=Phase.ETH,
        phase_probs={"btc": 0.3, "eth": 0.5, "large": 0.15, "alt": 0.05},
        confidence=0.7,
        explain=["ETH surperforme", "Transition positive"],
        persistence_count=2
    )


class TestTemplateLoading:
    """Tests de chargement des templates"""
    
    @pytest.mark.asyncio
    async def test_load_fallback_templates(self, strategy_registry):
        """Test chargement des templates par défaut"""
        success = await strategy_registry.load_templates()
        
        assert success
        assert len(strategy_registry.templates) >= 3
        assert "balanced" in strategy_registry.templates
        assert "conservative" in strategy_registry.templates
        assert "aggressive" in strategy_registry.templates
        
        # Vérifier structure template
        balanced = strategy_registry.templates["balanced"]
        assert balanced.name == "Balanced"
        assert balanced.template == StrategyTemplate.BALANCED
        assert isinstance(balanced.weights, StrategyWeights)
        assert isinstance(balanced.risk_budget, dict)
    
    @pytest.mark.asyncio
    async def test_load_custom_config(self, strategy_registry, temp_config_path):
        """Test chargement config custom depuis fichier"""
        # Créer config test
        config_data = {
            "templates": {
                "test_template": {
                    "name": "Test Template",
                    "template": "custom",
                    "weights": {
                        "cycle": 0.4,
                        "onchain": 0.3,
                        "risk_adjusted": 0.2,
                        "sentiment": 0.1
                    },
                    "risk_budget": {"volatility": 0.15},
                    "phase_adjustments": {"btc": 1.0, "eth": 1.2},
                    "confidence_threshold": 0.6,
                    "rebalance_threshold_pct": 0.04,
                    "description": "Template de test"
                }
            },
            "version": "test"
        }
        
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        success = await strategy_registry.load_templates()
        
        assert success
        assert "test_template" in strategy_registry.templates
        template = strategy_registry.templates["test_template"]
        assert template.name == "Test Template"
        assert template.weights.cycle == 0.4
        assert template.description == "Template de test"
    
    @pytest.mark.asyncio
    async def test_template_weights_normalization(self, strategy_registry):
        """Test normalisation automatique des poids"""
        await strategy_registry.load_templates()
        
        for template_id, template in strategy_registry.templates.items():
            weights = template.weights
            total_weight = (
                weights.cycle + weights.onchain + 
                weights.risk_adjusted + weights.sentiment
            )
            # Poids normalisés doivent sommer à ~1.0
            assert abs(total_weight - 1.0) < 0.001, f"Template {template_id} mal normalisé: {total_weight}"
    
    def test_get_available_templates(self, strategy_registry):
        """Test récupération templates disponibles"""
        # Utiliser fallback templates
        strategy_registry.templates = strategy_registry.fallback_templates
        
        available = strategy_registry.get_available_templates()
        
        assert isinstance(available, dict)
        assert len(available) >= 3
        
        for template_id, info in available.items():
            assert "name" in info
            assert "description" in info  
            assert "template" in info
            assert "risk_level" in info
            assert info["risk_level"] in ["low", "medium", "high"]


class TestStrategyCalculation:
    """Tests du calcul de stratégie"""
    
    @pytest.mark.asyncio
    async def test_calculate_balanced_strategy(self, strategy_registry, mock_scores, mock_phase_state):
        """Test calcul stratégie balanced"""
        await strategy_registry.load_templates()
        
        # Mock des dépendances
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', return_value=mock_scores), \
             patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=mock_phase_state):
            
            result = await strategy_registry.calculate_strategy("balanced", force_refresh=True)
            
            assert result.strategy_used == "Balanced"
            assert 0 <= result.decision_score <= 100
            assert 0 <= result.confidence <= 1
            assert len(result.targets) > 0
            assert len(result.rationale) >= 2
            assert result.policy_hint in ["Slow", "Normal", "Aggressive"]
            
            # Vérifier normalisation des poids
            total_weight = sum(t.weight for t in result.targets)
            assert abs(total_weight - 1.0) < 0.01
    
    @pytest.mark.asyncio
    async def test_strategy_phase_adjustments(self, strategy_registry, mock_scores):
        """Test ajustements par phase"""
        await strategy_registry.load_templates()
        
        # Mock phase BTC vs ALT pour comparer
        phase_btc = PhaseState(
            phase_now=Phase.BTC, phase_probs={"btc": 0.8, "eth": 0.1, "large": 0.05, "alt": 0.05},
            confidence=0.8, explain=["Phase BTC"], persistence_count=3
        )
        
        phase_alt = PhaseState(
            phase_now=Phase.ALT, phase_probs={"btc": 0.1, "eth": 0.1, "large": 0.2, "alt": 0.6},
            confidence=0.7, explain=["Phase ALT"], persistence_count=2
        )
        
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', return_value=mock_scores):
            # Test phase BTC
            with patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=phase_btc):
                result_btc = await strategy_registry.calculate_strategy("aggressive", force_refresh=True)
            
            # Test phase ALT  
            with patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=phase_alt):
                result_alt = await strategy_registry.calculate_strategy("aggressive", force_refresh=True)
            
            # Phase ALT devrait avoir score plus élevé avec template aggressive
            # (car phase_adjustments["alt"] = 1.3 vs "btc" = 0.9)
            assert result_alt.decision_score > result_btc.decision_score
    
    @pytest.mark.asyncio
    async def test_custom_weights_override(self, strategy_registry, mock_scores, mock_phase_state):
        """Test override poids custom"""
        await strategy_registry.load_templates()
        
        custom_weights = {
            "cycle": 0.5,      # Très élevé
            "onchain": 0.3,
            "risk_adjusted": 0.1,  # Très faible
            "sentiment": 0.1
        }
        
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', return_value=mock_scores), \
             patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=mock_phase_state):
            
            result = await strategy_registry.calculate_strategy(
                "balanced", custom_weights=custom_weights, force_refresh=True
            )
            
            # Doit utiliser les poids custom (vérifiable via le score final qui change)
            assert result.strategy_used == "Balanced"
            assert len(result.targets) > 0
    
    @pytest.mark.asyncio
    async def test_strategy_error_fallback(self, strategy_registry):
        """Test fallback en cas d'erreur"""
        await strategy_registry.load_templates()
        
        # Mock erreurs dans les dépendances
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', side_effect=Exception("Test error")), \
             patch.object(strategy_registry.phase_engine, 'get_current_phase', side_effect=Exception("Phase error")):
            
            result = await strategy_registry.calculate_strategy("balanced", force_refresh=True)
            
            # Doit retourner fallback sécurisé
            assert result.strategy_used == "Fallback"
            assert result.decision_score == 50.0
            assert result.confidence == 0.1
            assert result.policy_hint == "Slow"
            assert len(result.targets) >= 1
            assert result.targets[0].symbol == "BTC"  # Allocation sécurisée


class TestAllocationGeneration:
    """Tests de génération d'allocations"""
    
    def test_conservative_allocation(self, strategy_registry):
        """Test allocation conservative (score bas)"""
        strategy_registry.templates = strategy_registry.fallback_templates
        config = strategy_registry.templates["conservative"]
        
        # Score bas (< 30)
        mock_phase = PhaseState(Phase.BTC, {"btc": 0.7}, 0.6, ["BTC phase"], 1)
        
        targets = strategy_registry._generate_allocation_targets(25.0, mock_phase, config)
        
        # Allocation conservative: majorité BTC + stables
        btc_weight = next((t.weight for t in targets if t.symbol == "BTC"), 0)
        stable_weight = next((t.weight for t in targets if t.symbol == "USDC"), 0)
        
        assert btc_weight > 0.3  # Au moins 30% BTC
        assert stable_weight > 0.3  # Au moins 30% stables
        
        # Poids normalisés
        total_weight = sum(t.weight for t in targets)
        assert abs(total_weight - 1.0) < 0.01
    
    def test_aggressive_alt_allocation(self, strategy_registry):
        """Test allocation agressive en phase ALT"""
        strategy_registry.templates = strategy_registry.fallback_templates
        config = strategy_registry.templates["aggressive"]
        
        # Score élevé + phase ALT
        mock_phase = PhaseState(Phase.ALT, {"alt": 0.6, "btc": 0.1}, 0.8, ["ALT season"], 3)
        
        targets = strategy_registry._generate_allocation_targets(80.0, mock_phase, config)
        
        # Phase ALT: doit avoir allocation ALT
        alt_weight = next((t.weight for t in targets if t.symbol == "ALT"), 0)
        btc_weight = next((t.weight for t in targets if t.symbol == "BTC"), 0)
        
        assert alt_weight > 0.2  # Au moins 20% ALT
        assert btc_weight < 0.3  # BTC réduit en phase ALT
        
        # Vérifier diversification (au moins 3 assets)
        assert len(targets) >= 3
    
    def test_phase_specific_allocations(self, strategy_registry):
        """Test allocations spécifiques par phase"""
        strategy_registry.templates = strategy_registry.fallback_templates
        config = strategy_registry.templates["balanced"]
        
        phases_to_test = [
            (Phase.BTC, "BTC"),
            (Phase.ETH, "ETH"), 
            (Phase.LARGE, "LARGE"),
            (Phase.ALT, "ALT")
        ]
        
        for phase_enum, expected_symbol in phases_to_test:
            mock_phase = PhaseState(phase_enum, {phase_enum.value: 0.7}, 0.7, [f"Phase {phase_enum.value}"], 2)
            
            targets = strategy_registry._generate_allocation_targets(70.0, mock_phase, config)
            
            # Le symbole de la phase doit avoir poids significatif
            phase_weight = next((t.weight for t in targets if t.symbol == expected_symbol), 0)
            assert phase_weight > 0.2, f"Phase {phase_enum.value}: poids {expected_symbol} trop faible ({phase_weight})"


class TestPolicyHints:
    """Tests des policy hints"""
    
    def test_policy_hint_slow_conditions(self, strategy_registry):
        """Test conditions pour policy Slow"""
        # Contradictions élevées
        hint1 = strategy_registry._determine_policy_hint(60.0, 0.6, 0.7)  # contradiction > 0.6
        assert hint1 == "Slow"
        
        # Confiance faible
        hint2 = strategy_registry._determine_policy_hint(70.0, 0.3, 0.2)  # confidence < 0.4
        assert hint2 == "Slow"
    
    def test_policy_hint_aggressive_conditions(self, strategy_registry):
        """Test conditions pour policy Aggressive"""
        # Score et confiance élevés
        hint = strategy_registry._determine_policy_hint(80.0, 0.8, 0.1)  # score > 75, confidence > 0.7
        assert hint == "Aggressive"
    
    def test_policy_hint_normal_default(self, strategy_registry):
        """Test policy Normal par défaut"""
        hint = strategy_registry._determine_policy_hint(60.0, 0.6, 0.3)  # Conditions moyennes
        assert hint == "Normal"


class TestCacheAndPerformance:
    """Tests du cache et performances"""
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, strategy_registry, mock_scores, mock_phase_state):
        """Test fonctionnement du cache TTL"""
        await strategy_registry.load_templates()
        
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', return_value=mock_scores) as mock_score, \
             patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=mock_phase_state) as mock_phase:
            
            # Premier appel
            result1 = await strategy_registry.calculate_strategy("balanced")
            assert mock_score.call_count == 1
            assert mock_phase.call_count == 1
            
            # Deuxième appel immédiat : doit utiliser le cache
            result2 = await strategy_registry.calculate_strategy("balanced")
            assert mock_score.call_count == 1  # Pas d'appel supplémentaire
            assert mock_phase.call_count == 1
            
            # Résultats identiques via cache
            assert result1.decision_score == result2.decision_score
            assert result1.generated_at == result2.generated_at
    
    @pytest.mark.asyncio
    async def test_force_refresh_bypass_cache(self, strategy_registry, mock_scores, mock_phase_state):
        """Test bypass du cache avec force_refresh"""
        await strategy_registry.load_templates()
        
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', return_value=mock_scores) as mock_score, \
             patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=mock_phase_state) as mock_phase:
            
            # Premier appel
            result1 = await strategy_registry.calculate_strategy("balanced")
            
            # Force refresh: doit bypasser le cache
            result2 = await strategy_registry.calculate_strategy("balanced", force_refresh=True)
            
            assert mock_score.call_count == 2  # 2 appels
            assert mock_phase.call_count == 2


class TestRiskAssessment:
    """Tests d'évaluation du risque"""
    
    def test_risk_level_assessment(self, strategy_registry):
        """Test évaluation niveau de risque des templates"""
        # Template conservateur
        conservative_config = StrategyConfig(
            name="Test Conservative",
            template=StrategyTemplate.CONSERVATIVE,
            weights=StrategyWeights(cycle=0.2, onchain=0.2, risk_adjusted=0.5, sentiment=0.1),
            risk_budget={}, phase_adjustments={}
        )
        
        risk_level = strategy_registry._assess_risk_level(conservative_config)
        assert risk_level == "low"
        
        # Template agressif
        aggressive_config = StrategyConfig(
            name="Test Aggressive", 
            template=StrategyTemplate.AGGRESSIVE,
            weights=StrategyWeights(cycle=0.5, onchain=0.4, risk_adjusted=0.05, sentiment=0.05),
            risk_budget={}, phase_adjustments={}
        )
        
        risk_level = strategy_registry._assess_risk_level(aggressive_config)
        assert risk_level in ["medium", "high"]  # Peut être medium selon thresholds


class TestHealthCheck:
    """Tests du health check"""
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, strategy_registry):
        """Test health check quand tout va bien"""
        await strategy_registry.load_templates()
        
        health = await strategy_registry.health_check()
        
        assert health["status"] == "healthy"
        assert health["templates_loaded"] >= 3
        assert "config_loaded_at" in health
        assert "timestamp" in health
        assert isinstance(health["cache_size"], int)
    
    @pytest.mark.asyncio
    async def test_health_check_degraded(self, strategy_registry):
        """Test health check en mode dégradé"""
        # Pas de templates chargés
        health = await strategy_registry.health_check()
        
        assert health["status"] == "degraded"
        assert health["templates_loaded"] == 0


class TestSingleton:
    """Tests du pattern singleton"""
    
    def test_singleton_pattern(self):
        """Test que get_strategy_registry retourne toujours la même instance"""
        registry1 = get_strategy_registry()
        registry2 = get_strategy_registry()
        
        assert registry1 is registry2  # Même instance


# Tests d'intégration légers
class TestIntegration:
    """Tests d'intégration avec composants réels"""
    
    @pytest.mark.asyncio
    async def test_realistic_strategy_calculation(self, strategy_registry):
        """Test calcul stratégie avec mocks réalistes"""
        await strategy_registry.load_templates()
        
        # Simuler des scores réalistes de marché bull modéré
        realistic_scores = CanonicalScores(
            decision=72.5,
            confidence=0.75,
            contradiction=0.15,
            components=ScoreComponents(
                trend_regime=75.0,
                risk=35.0,  # Risk faible (bullish)
                breadth_rotation=70.0,
                sentiment=65.0
            ),
            as_of=datetime.now()
        )
        
        realistic_phase = PhaseState(
            phase_now=Phase.LARGE,
            phase_probs={"btc": 0.2, "eth": 0.3, "large": 0.4, "alt": 0.1},
            confidence=0.8,
            explain=["Large caps momentum", "Rotation confirmée"],
            persistence_count=3
        )
        
        with patch.object(strategy_registry.score_registry, 'calculate_canonical_score', return_value=realistic_scores), \
             patch.object(strategy_registry.phase_engine, 'get_current_phase', return_value=realistic_phase):
            
            result = await strategy_registry.calculate_strategy("balanced", force_refresh=True)
            
            # Vérifications réalistes
            assert 60.0 <= result.decision_score <= 85.0  # Score bull modéré
            assert result.confidence >= 0.6  # Confiance raisonnable
            assert result.policy_hint in ["Normal", "Aggressive"]  # Pas Slow avec ce setup
            
            # Allocation LARGE devrait être significative en phase LARGE
            large_allocation = next((t.weight for t in result.targets if t.symbol == "LARGE"), 0)
            assert large_allocation > 0.2  # Au moins 20% en LARGE caps
            
            # Rationale doit mentionner la phase
            rationale_text = " ".join(result.rationale).lower()
            assert "large" in rationale_text or "phase" in rationale_text