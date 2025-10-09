"""
Tests Edge Cases & Monotonicité - Risk Scoring (Oct 2025)

Valide les propriétés critiques après l'adoucissement des pénalités :
- Monotonicité des pénalités (memes, DD, HHI, GRI)
- Pas de score=0 systématique sur portfolios degen
- Bornes [0, 100] respectées
- Stabilité des transitions
"""

import pytest
from services.risk_scoring import assess_risk_level


class TestMonotonicity:
    """Test que les pénalités augmentent de manière monotone"""

    def test_memecoins_monotonicity_below_threshold(self):
        """Memecoins 49% → 51% doit diminuer le score (franchissement seuil >50%)"""
        base_metrics = {
            "var_95": 0.10, "var_99": 0.15,
            "sharpe": 0.5, "max_dd": -0.25, "vol": 0.45,
            "hhi": 0.12, "gri": 5.0, "div": 1.0
        }

        # 49% memecoins (sous seuil 50%)
        result_below = assess_risk_level(
            var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
            sharpe_ratio=base_metrics["sharpe"],
            max_drawdown=base_metrics["max_dd"],
            volatility=base_metrics["vol"],
            memecoins_pct=0.49,
            hhi=base_metrics["hhi"],
            gri=base_metrics["gri"],
            diversification_ratio=base_metrics["div"]
        )

        # 51% memecoins (au-dessus seuil 50%)
        result_above = assess_risk_level(
            var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
            sharpe_ratio=base_metrics["sharpe"],
            max_drawdown=base_metrics["max_dd"],
            volatility=base_metrics["vol"],
            memecoins_pct=0.51,
            hhi=base_metrics["hhi"],
            gri=base_metrics["gri"],
            diversification_ratio=base_metrics["div"]
        )

        # Score doit diminuer après franchissement du seuil
        assert result_below["score"] > result_above["score"], \
            f"49% memes ({result_below['score']:.1f}) devrait scorer plus que 51% ({result_above['score']:.1f})"

        # Vérifier breakdown
        assert result_below["breakdown"]["memecoins"] > result_above["breakdown"]["memecoins"], \
            "Pénalité memes doit augmenter après 50%"

    def test_drawdown_monotonicity(self):
        """DD 45% → 62% doit diminuer le score sans clamp à 0"""
        base_metrics = {
            "var_95": 0.08, "var_99": 0.12,
            "sharpe": 0.6, "vol": 0.40,
            "memes": 0.10, "hhi": 0.10, "gri": 4.0, "div": 1.0
        }

        # DD 45% (entre 30-50%)
        result_moderate = assess_risk_level(
            var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
            sharpe_ratio=base_metrics["sharpe"],
            max_drawdown=-0.45,
            volatility=base_metrics["vol"],
            memecoins_pct=base_metrics["memes"],
            hhi=base_metrics["hhi"],
            gri=base_metrics["gri"],
            diversification_ratio=base_metrics["div"]
        )

        # DD 62% (>50%)
        result_severe = assess_risk_level(
            var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
            sharpe_ratio=base_metrics["sharpe"],
            max_drawdown=-0.62,
            volatility=base_metrics["vol"],
            memecoins_pct=base_metrics["memes"],
            hhi=base_metrics["hhi"],
            gri=base_metrics["gri"],
            diversification_ratio=base_metrics["div"]
        )

        # Score doit diminuer avec DD plus élevé
        assert result_moderate["score"] > result_severe["score"], \
            f"DD 45% ({result_moderate['score']:.1f}) devrait scorer plus que DD 62% ({result_severe['score']:.1f})"

        # IMPORTANT : Score ne doit pas être 0
        assert result_severe["score"] > 0, \
            f"DD 62% ne devrait pas clamper à 0 (score actuel: {result_severe['score']:.1f})"

    def test_hhi_gri_progressive_penalties(self):
        """HHI et GRI doivent pénaliser progressivement, pas brutalement"""
        base_metrics = {
            "var_95": 0.08, "var_99": 0.12,
            "sharpe": 0.7, "max_dd": -0.25, "vol": 0.40,
            "memes": 0.08, "div": 1.0
        }

        # Portfolio bien diversifié
        result_good = assess_risk_level(
            var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
            sharpe_ratio=base_metrics["sharpe"],
            max_drawdown=base_metrics["max_dd"],
            volatility=base_metrics["vol"],
            memecoins_pct=base_metrics["memes"],
            hhi=0.10,  # Faible concentration
            gri=4.0,   # Groupes peu risqués
            diversification_ratio=base_metrics["div"]
        )

        # Portfolio concentré + groupes risqués
        result_risky = assess_risk_level(
            var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
            sharpe_ratio=base_metrics["sharpe"],
            max_drawdown=base_metrics["max_dd"],
            volatility=base_metrics["vol"],
            memecoins_pct=base_metrics["memes"],
            hhi=0.30,  # Concentration élevée
            gri=7.5,   # Groupes très risqués
            diversification_ratio=base_metrics["div"]
        )

        # Score doit diminuer mais rester > 0
        assert result_good["score"] > result_risky["score"], \
            "Portfolio diversifié doit scorer mieux que portfolio concentré"
        assert result_risky["score"] > 0, \
            "Portfolio concentré ne devrait pas clamper à 0"


class TestDegenPortfolios:
    """Test que portfolios degen scorent entre 10-25, pas 0"""

    def test_degen_portfolio_scores_above_zero(self):
        """Portfolio degen (55% memes, DD 61%) doit scorer 10-20, pas 0"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.0624, "var_99": 0.0962, "cvar_95": 0.0799, "cvar_99": 0.1299},
            sharpe_ratio=0.33,
            max_drawdown=-0.617,
            volatility=0.6496,
            memecoins_pct=0.5499,
            hhi=0.218,
            gri=7.44,
            diversification_ratio=1.09
        )

        assert result["score"] > 0, "Portfolio degen ne doit pas scorer 0"
        assert 10 <= result["score"] <= 25, \
            f"Portfolio degen devrait scorer 10-25, pas {result['score']:.1f}"
        assert result["level"] == "critical", \
            f"Portfolio degen devrait être 'critical', pas '{result['level']}'"

    def test_extreme_degen_portfolio_acceptable_zero(self):
        """Portfolio degen extrême (75% memes, DD 80%, Sharpe négatif) peut scorer 0 (catastrophique)"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.15, "var_99": 0.25},
            sharpe_ratio=-0.2,  # ❌ Sharpe négatif
            max_drawdown=-0.80,  # ❌ DD 80%
            volatility=0.85,     # ❌ Vol 85%
            memecoins_pct=0.75,  # ❌ 75% memes
            hhi=0.35,            # ❌ Concentré
            gri=8.5,             # ❌ Groupes très risqués
            diversification_ratio=0.5  # ❌ Faible diversification
        )

        # Ce portfolio est tellement catastrophique qu'un score 0 est acceptable
        assert result["score"] >= 0, "Score ne doit jamais être négatif"
        assert result["score"] <= 5, "Portfolio catastrophique doit scorer ≤ 5"
        assert result["level"] == "critical"


class TestBoundsAndClamps:
    """Test que les scores restent dans [0, 100]"""

    def test_score_never_negative(self):
        """Score ne doit jamais être négatif"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.30, "var_99": 0.50},
            sharpe_ratio=-0.5,
            max_drawdown=-0.90,
            volatility=1.5,
            memecoins_pct=0.80,
            hhi=0.50,
            gri=9.0,
            diversification_ratio=0.3
        )

        assert result["score"] >= 0, f"Score ne doit jamais être négatif (got {result['score']:.1f})"

    def test_score_never_above_100(self):
        """Score ne doit jamais dépasser 100"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.02, "var_99": 0.03},
            sharpe_ratio=3.0,
            max_drawdown=-0.05,
            volatility=0.15,
            memecoins_pct=0.0,
            hhi=0.05,
            gri=2.0,
            diversification_ratio=1.5
        )

        assert result["score"] <= 100, f"Score ne doit jamais dépasser 100 (got {result['score']:.1f})"

    def test_excellent_portfolio_high_score(self):
        """Portfolio excellent doit scorer 80-100"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.03, "var_99": 0.05},
            sharpe_ratio=2.5,
            max_drawdown=-0.08,
            volatility=0.18,
            memecoins_pct=0.0,
            hhi=0.08,
            gri=2.5,
            diversification_ratio=1.2
        )

        assert 80 <= result["score"] <= 100, \
            f"Portfolio excellent devrait scorer 80-100, pas {result['score']:.1f}"
        assert result["level"] in ["very_low", "low"]


class TestTransitionStability:
    """Test que les transitions sont stables (pas de sauts brutaux)"""

    def test_memecoins_transition_gradual(self):
        """Transition 30% → 50% → 70% memes doit être progressive"""
        base_metrics = {
            "var_95": 0.08, "var_99": 0.12,
            "sharpe": 0.6, "max_dd": -0.30, "vol": 0.45,
            "hhi": 0.12, "gri": 5.0, "div": 1.0
        }

        scores = []
        for memes_pct in [0.25, 0.35, 0.55, 0.75]:
            result = assess_risk_level(
                var_metrics={"var_95": base_metrics["var_95"], "var_99": base_metrics["var_99"]},
                sharpe_ratio=base_metrics["sharpe"],
                max_drawdown=base_metrics["max_dd"],
                volatility=base_metrics["vol"],
                memecoins_pct=memes_pct,
                hhi=base_metrics["hhi"],
                gri=base_metrics["gri"],
                diversification_ratio=base_metrics["div"]
            )
            scores.append(result["score"])

        # Scores doivent être monotones décroissants
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], \
                f"Scores devraient décroître monotonement : {scores}"

        # Pas de sauts > 20 points entre paliers adjacents
        for i in range(len(scores) - 1):
            diff = abs(scores[i] - scores[i + 1])
            assert diff <= 20, \
                f"Saut trop brutal ({diff:.1f}) entre {memes_pct*100:.0f}% et {(memes_pct+0.2)*100:.0f}%"


class TestBreakdownConsistency:
    """Test que le breakdown est cohérent avec le score final"""

    def test_breakdown_sums_to_score(self):
        """Somme des deltas du breakdown doit égaler score - 50"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.08, "var_99": 0.12},
            sharpe_ratio=0.7,
            max_drawdown=-0.25,
            volatility=0.40,
            memecoins_pct=0.15,
            hhi=0.18,
            gri=5.5,
            diversification_ratio=0.9
        )

        breakdown_sum = sum(result["breakdown"].values())
        expected_score = 50 + breakdown_sum

        assert abs(result["score"] - expected_score) < 0.01, \
            f"Score {result['score']:.1f} != 50 + breakdown ({expected_score:.1f})"

    def test_breakdown_keys_complete(self):
        """Breakdown doit contenir toutes les clés attendues"""
        result = assess_risk_level(
            var_metrics={"var_95": 0.08, "var_99": 0.12},
            sharpe_ratio=0.6,
            max_drawdown=-0.25,
            volatility=0.40,
            memecoins_pct=0.10,
            hhi=0.15,
            gri=5.0,
            diversification_ratio=1.0
        )

        expected_keys = {
            "var_95", "sharpe", "drawdown", "volatility",
            "memecoins", "concentration", "group_risk", "diversification"
        }

        assert set(result["breakdown"].keys()) == expected_keys, \
            f"Clés manquantes ou supplémentaires: {result['breakdown'].keys()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
