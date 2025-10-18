"""
Unit tests for Bourse Alerts System

Tests alert detection logic, threshold validation, and alert generation
for moderate risk profile.
"""

import pytest
from services.risk.bourse.alerts import BourseAlertsDetector


class TestBourseAlertsDetector:
    """Test suite for BourseAlertsDetector"""

    @pytest.fixture
    def detector(self):
        """Create a fresh detector instance for each test"""
        return BourseAlertsDetector()

    @pytest.fixture
    def healthy_portfolio_data(self):
        """Sample data for a healthy portfolio (no alerts expected)"""
        return {
            'risk': {
                'score': 65.0,
                'level': 'LOW',
                'metrics': {
                    'var_95_1d': -0.0189,      # -1.89% (< 4% threshold)
                    'max_drawdown': -0.0307,    # -3.07% (> -18% threshold)
                    'sharpe_ratio': 2.22,       # > 0.8 threshold
                    'beta_portfolio': 0.90,     # Within 0.3-1.6 range
                }
            },
            'coverage': 1.0,
            'positions_count': 28,
            'total_value_usd': 106749
        }

    @pytest.fixture
    def risky_portfolio_data(self):
        """Sample data for a risky portfolio (multiple alerts expected)"""
        return {
            'risk': {
                'score': 35.0,
                'level': 'HIGH',
                'metrics': {
                    'var_95_1d': -0.05,        # -5% (> 4% threshold) → CRITICAL
                    'max_drawdown': -0.20,      # -20% (< -18% threshold) → CRITICAL
                    'sharpe_ratio': 0.5,        # < 0.8 threshold → WARNING
                    'beta_portfolio': 1.8,      # > 1.6 threshold → CRITICAL
                }
            },
            'coverage': 0.8,
            'positions_count': 15,
            'total_value_usd': 50000
        }

    # ==================== Critical Alert Tests ====================

    def test_no_alerts_healthy_portfolio(self, detector, healthy_portfolio_data):
        """Test that healthy portfolio generates no alerts"""
        result = detector.detect_alerts(healthy_portfolio_data)

        assert result['summary']['total'] == 0
        assert result['summary']['critical'] == 0
        assert result['summary']['warning'] == 0
        assert result['summary']['info'] == 0
        assert len(result['critical']) == 0
        assert len(result['warnings']) == 0
        assert len(result['info']) == 0

    def test_critical_var_alert(self, detector):
        """Test critical VaR alert (> 4%)"""
        data = {
            'risk': {
                'score': 40.0,
                'metrics': {
                    'var_95_1d': -0.045,  # -4.5% (> 4% threshold)
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['critical'] >= 1
        critical_alerts = [a for a in result['critical'] if a['type'] == 'high_var']
        assert len(critical_alerts) == 1
        assert critical_alerts[0]['severity'] == 'critical'
        assert '4.50%' in critical_alerts[0]['value']

    def test_critical_drawdown_alert(self, detector):
        """Test critical drawdown alert (< -18%)"""
        data = {
            'risk': {
                'score': 30.0,
                'metrics': {
                    'max_drawdown': -0.22,  # -22% (< -18% threshold)
                    'drawdown_days': 45
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['critical'] >= 1
        critical_alerts = [a for a in result['critical'] if a['type'] == 'critical_drawdown']
        assert len(critical_alerts) == 1
        assert critical_alerts[0]['severity'] == 'critical'
        assert '-22.00%' in critical_alerts[0]['value']
        assert '45 jours' in critical_alerts[0]['impact']

    def test_critical_beta_high_alert(self, detector):
        """Test critical beta alert (> 1.6)"""
        data = {
            'risk': {
                'score': 45.0,
                'metrics': {
                    'beta_portfolio': 1.85,  # > 1.6 threshold
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['critical'] >= 1
        critical_alerts = [a for a in result['critical'] if a['type'] == 'high_beta']
        assert len(critical_alerts) == 1
        assert '1.85' in critical_alerts[0]['value']

    def test_critical_beta_low_alert(self, detector):
        """Test critical beta alert (< 0.3)"""
        data = {
            'risk': {
                'score': 45.0,
                'metrics': {
                    'beta_portfolio': 0.15,  # < 0.3 threshold
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['critical'] >= 1
        critical_alerts = [a for a in result['critical'] if a['type'] == 'low_beta']
        assert len(critical_alerts) == 1
        assert '0.15' in critical_alerts[0]['value']

    # ==================== Warning Alert Tests ====================

    def test_warning_var_alert(self, detector):
        """Test warning VaR alert (2.5-4%)"""
        data = {
            'risk': {
                'score': 50.0,
                'metrics': {
                    'var_95_1d': -0.03,  # -3% (between 2.5-4%)
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['warning'] >= 1
        warning_alerts = [a for a in result['warnings'] if a['type'] == 'elevated_var']
        assert len(warning_alerts) == 1
        assert warning_alerts[0]['severity'] == 'warning'

    def test_warning_drawdown_alert(self, detector):
        """Test warning drawdown alert (-12% to -18%)"""
        data = {
            'risk': {
                'score': 55.0,
                'metrics': {
                    'max_drawdown': -0.15,  # -15% (between -12% and -18%)
                    'drawdown_days': 30
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['warning'] >= 1
        warning_alerts = [a for a in result['warnings'] if a['type'] == 'elevated_drawdown']
        assert len(warning_alerts) == 1

    def test_warning_sharpe_alert(self, detector):
        """Test warning Sharpe ratio alert (< 0.8)"""
        data = {
            'risk': {
                'score': 52.0,
                'metrics': {
                    'sharpe_ratio': 0.6,  # < 0.8 threshold
                }
            }
        }

        result = detector.detect_alerts(data)

        assert result['summary']['warning'] >= 1
        warning_alerts = [a for a in result['warnings'] if a['type'] == 'low_sharpe']
        assert len(warning_alerts) == 1
        assert '0.60' in warning_alerts[0]['value']

    # ==================== Margin Alert Tests ====================

    def test_critical_margin_alert(self, detector):
        """Test critical margin alert (> 85%)"""
        data = {'risk': {'score': 50.0, 'metrics': {}}}
        specialized_data = {
            'margin': {
                'margin_utilization': 0.90,  # 90% (> 85%)
                'current_leverage': 4.0
            }
        }

        result = detector.detect_alerts(data, specialized_data=specialized_data)

        assert result['summary']['critical'] >= 1
        critical_alerts = [a for a in result['critical'] if a['type'] == 'margin_call_risk']
        assert len(critical_alerts) == 1
        assert '90.0%' in critical_alerts[0]['value']

    def test_warning_margin_alert(self, detector):
        """Test warning margin alert (70-85%)"""
        data = {'risk': {'score': 50.0, 'metrics': {}}}
        specialized_data = {
            'margin': {
                'margin_utilization': 0.75,  # 75% (between 70-85%)
                'margin_call_distance': 0.25,
                'current_leverage': 2.5
            }
        }

        result = detector.detect_alerts(data, specialized_data=specialized_data)

        assert result['summary']['warning'] >= 1
        warning_alerts = [a for a in result['warnings'] if a['type'] == 'margin_elevated']
        assert len(warning_alerts) == 1

    def test_no_margin_alert_cash_account(self, detector):
        """Test that cash accounts (margin=0) don't trigger margin alerts"""
        data = {'risk': {'score': 50.0, 'metrics': {}}}
        specialized_data = {
            'margin': {
                'margin_utilization': 0.0,  # 0% (cash account)
                'current_leverage': 1.0
            }
        }

        result = detector.detect_alerts(data, specialized_data=specialized_data)

        # Should have NO margin alerts
        margin_alerts = [a for a in result['critical'] + result['warnings']
                        if a['type'] in ['margin_call_risk', 'margin_elevated']]
        assert len(margin_alerts) == 0

    # ==================== Concentration Alert Tests ====================

    def test_sector_concentration_alert(self, detector):
        """Test sector concentration alert (> 35%)"""
        data = {'risk': {'score': 50.0, 'metrics': {}}}
        specialized_data = {
            'sectors': {
                'Technology': {
                    'weight': 0.42,  # 42% (> 35% threshold)
                    'top_tickers': ['AAPL', 'MSFT', 'NVDA']
                }
            }
        }

        result = detector.detect_alerts(data, specialized_data=specialized_data)

        assert result['summary']['warning'] >= 1
        warning_alerts = [a for a in result['warnings'] if a['type'] == 'sector_concentration']
        assert len(warning_alerts) >= 1
        assert 'Technology' in warning_alerts[0]['title']
        assert '42.0%' in warning_alerts[0]['value']

    # ==================== ML Alert Tests ====================

    def test_regime_change_info_alert(self, detector):
        """Test regime change info alert (>75% confidence)"""
        data = {'risk': {'score': 60.0, 'metrics': {}}}
        ml_data = {
            'regime': {
                'current_regime': 'Bear Market',
                'confidence': 0.85,  # 85% (> 75% threshold)
                'regime_probabilities': {
                    'Bear Market': 0.85,
                    'Consolidation': 0.10,
                    'Bull Market': 0.05
                }
            }
        }

        result = detector.detect_alerts(data, ml_data=ml_data)

        assert result['summary']['info'] >= 1
        info_alerts = [a for a in result['info'] if a['type'] == 'regime_change']
        assert len(info_alerts) == 1
        assert 'Bear Market' in info_alerts[0]['title']
        assert '85%' in info_alerts[0]['value']

    def test_high_vol_forecast_info_alert(self, detector):
        """Test high volatility forecast alert (+40% vol increase)"""
        data = {'risk': {'score': 60.0, 'metrics': {}}}
        ml_data = {
            'volatility_forecast': {
                '7d': {'predicted_volatility': 0.07},   # 7%
                '30d': {'predicted_volatility': 0.04},  # 4% → +75% increase
            }
        }

        result = detector.detect_alerts(data, ml_data=ml_data)

        assert result['summary']['info'] >= 1
        info_alerts = [a for a in result['info'] if a['type'] == 'high_vol_forecast']
        assert len(info_alerts) == 1

    # ==================== Multiple Alerts Tests ====================

    def test_multiple_critical_alerts(self, detector, risky_portfolio_data):
        """Test that risky portfolio generates multiple critical alerts"""
        result = detector.detect_alerts(risky_portfolio_data)

        # Should have multiple critical alerts
        assert result['summary']['critical'] >= 3
        assert result['summary']['warning'] >= 1

        # Check specific alerts
        alert_types = [a['type'] for a in result['critical']]
        assert 'high_var' in alert_types
        assert 'critical_drawdown' in alert_types
        assert 'high_beta' in alert_types

    def test_alert_structure(self, detector):
        """Test that alerts have required fields"""
        data = {
            'risk': {
                'score': 30.0,
                'metrics': {
                    'var_95_1d': -0.05,  # Critical alert
                }
            }
        }

        result = detector.detect_alerts(data)

        # Check result structure
        assert 'critical' in result
        assert 'warnings' in result
        assert 'info' in result
        assert 'summary' in result
        assert 'generated_at' in result

        # Check alert structure
        if len(result['critical']) > 0:
            alert = result['critical'][0]
            required_fields = [
                'type', 'severity', 'title', 'value', 'threshold',
                'impact', 'recommendation', 'action_deadline', 'created_at'
            ]
            for field in required_fields:
                assert field in alert, f"Missing field: {field}"

    # ==================== Edge Cases ====================

    def test_empty_risk_data(self, detector):
        """Test handling of empty risk data"""
        result = detector.detect_alerts({})

        # Should not crash, return empty alerts
        assert result['summary']['total'] == 0

    def test_missing_metrics(self, detector):
        """Test handling of missing metrics in risk data"""
        data = {
            'risk': {
                'score': 50.0,
                # No metrics field
            }
        }

        result = detector.detect_alerts(data)

        # Should not crash, just return no alerts for missing metrics
        assert isinstance(result, dict)
        assert 'summary' in result

    def test_none_ml_data(self, detector):
        """Test that None ML data doesn't cause errors"""
        data = {'risk': {'score': 50.0, 'metrics': {}}}

        result = detector.detect_alerts(data, ml_data=None)

        # Should work fine, just no ML alerts
        assert result['summary']['info'] == 0

    def test_none_specialized_data(self, detector):
        """Test that None specialized data doesn't cause errors"""
        data = {'risk': {'score': 50.0, 'metrics': {}}}

        result = detector.detect_alerts(data, specialized_data=None)

        # Should work fine, just no specialized alerts
        margin_alerts = [a for a in result['critical'] + result['warnings']
                        if 'margin' in a['type']]
        assert len(margin_alerts) == 0


# ==================== Integration Tests ====================

class TestAlertsIntegration:
    """Integration tests for full alert workflow"""

    def test_realistic_portfolio_scenario(self):
        """Test with realistic portfolio data"""
        detector = BourseAlertsDetector()

        # Realistic moderate-risk portfolio
        data = {
            'risk': {
                'score': 64.5,
                'level': 'LOW',
                'metrics': {
                    'var_95_1d': -0.0189,
                    'volatility_30d': 0.0609,
                    'volatility_252d': 0.1125,
                    'sharpe_ratio': 2.22,
                    'sortino_ratio': 3.15,
                    'max_drawdown': -0.0307,
                    'beta_portfolio': 0.90,
                    'calmar_ratio': 2.8
                }
            },
            'coverage': 1.0,
            'positions_count': 28,
            'total_value_usd': 106749
        }

        result = detector.detect_alerts(data)

        # Healthy portfolio should have minimal/no alerts
        assert result['summary']['critical'] == 0
        assert result['summary']['total'] <= 2  # Maybe 1-2 info alerts at most

    def test_crisis_portfolio_scenario(self):
        """Test portfolio during market crisis"""
        detector = BourseAlertsDetector()

        # Portfolio during COVID-like crisis
        data = {
            'risk': {
                'score': 25.0,
                'level': 'CRITICAL',
                'metrics': {
                    'var_95_1d': -0.08,        # -8% daily VaR
                    'max_drawdown': -0.34,      # -34% drawdown
                    'sharpe_ratio': -0.5,       # Negative Sharpe
                    'beta_portfolio': 1.5,      # High beta
                }
            },
            'coverage': 0.7,
            'positions_count': 20,
            'total_value_usd': 50000
        }

        result = detector.detect_alerts(data)

        # Crisis portfolio should have many alerts
        assert result['summary']['critical'] >= 2
        assert result['summary']['total'] >= 2  # At least 2 critical alerts


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
