"""
Bourse Risk Alerts System

Detects and generates risk alerts based on portfolio metrics for moderate risk profile.
Designed for medium-long term investing with active weekly management.

Alert Levels:
- CRITICAL: Immediate action required (this week)
- WARNING: Monitor and plan action (2-4 weeks)
- INFO: Opportunities and context (1-3 months)
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BourseAlertsDetector:
    """
    Detects risk alerts for bourse portfolio based on moderate risk profile.

    Calibrated for:
    - Horizon: Medium-Long term (6+ months)
    - Risk Profile: Moderate (balanced growth/risk)
    - Management: Active weekly (sector rotation, rebalancing)
    """

    # Thresholds for MODERATE risk profile
    THRESHOLDS = {
        # Critical (immediate action required)
        'critical': {
            'var_95_1d': 0.04,          # 4% VaR (more tolerant than conservative)
            'max_drawdown': -0.18,      # -18% drawdown
            'margin_utilization': 0.85,  # 85% margin
            'beta_high': 1.6,           # Beta too high (high correlation)
            'beta_low': 0.3,            # Beta too low (decorrelated)
        },
        # Warning (monitor and plan action)
        'warning': {
            'var_95_1d_min': 0.025,     # 2.5-4% VaR range
            'var_95_1d_max': 0.04,
            'max_drawdown_min': -0.18,  # -12% to -18% drawdown range
            'max_drawdown_max': -0.12,
            'concentration_top5': 0.55,  # 55% in top 5 positions
            'concentration_sector': 0.35, # 35% in single sector
            'margin_utilization_min': 0.70,
            'margin_utilization_max': 0.85,
            'sharpe_ratio': 0.8,        # Sharpe < 0.8 suboptimal
        },
        # Info (opportunities and context)
        'info': {
            'regime_confidence': 0.75,   # 75% confidence for regime change
            'vol_increase': 0.40,        # 40% volatility increase forecast
        }
    }

    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []

    def detect_alerts(
        self,
        risk_data: Dict[str, Any],
        ml_data: Optional[Dict[str, Any]] = None,
        specialized_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect all alerts based on current portfolio metrics.

        Args:
            risk_data: Risk metrics from /api/risk/bourse/dashboard
            ml_data: ML predictions (optional, for regime alerts)
            specialized_data: Specialized analytics (optional, for sector/margin)

        Returns:
            Dict with categorized alerts and summary
        """
        self.alerts = []

        # Extract metrics
        metrics = risk_data.get('risk', {}).get('metrics', {})

        # Critical alerts
        self._check_critical_var(metrics)
        self._check_critical_drawdown(metrics)
        self._check_critical_beta(metrics)

        # Warning alerts
        self._check_warning_var(metrics)
        self._check_warning_drawdown(metrics)
        self._check_warning_sharpe(metrics)

        # Specialized alerts (if data available)
        if specialized_data:
            self._check_margin_alerts(specialized_data)
            self._check_concentration_alerts(specialized_data)

        # ML alerts (if data available)
        if ml_data:
            self._check_regime_change_alert(ml_data)
            self._check_volatility_forecast_alert(ml_data)

        # Categorize alerts
        critical = [a for a in self.alerts if a['severity'] == 'critical']
        warnings = [a for a in self.alerts if a['severity'] == 'warning']
        info = [a for a in self.alerts if a['severity'] == 'info']

        return {
            'critical': critical,
            'warnings': warnings,
            'info': info,
            'summary': {
                'total': len(self.alerts),
                'critical': len(critical),
                'warning': len(warnings),
                'info': len(info)
            },
            'generated_at': datetime.utcnow().isoformat() + 'Z'
        }

    # === CRITICAL ALERTS ===

    def _check_critical_var(self, metrics: Dict[str, Any]):
        """Check for critical VaR (> 4%)"""
        var_95 = abs(metrics.get('var_95_1d', 0))
        threshold = self.THRESHOLDS['critical']['var_95_1d']

        if var_95 > threshold:
            self.alerts.append({
                'type': 'high_var',
                'severity': 'critical',
                'title': 'VaR Critique',
                'value': f'{var_95*100:.2f}%',
                'threshold': f'{threshold*100:.1f}%',
                'impact': f'Perte maximale probable: {var_95*100:.1f}%/jour',
                'recommendation': 'Réduire exposition immédiatement ou augmenter hedging',
                'action_deadline': 'Cette semaine',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    def _check_critical_drawdown(self, metrics: Dict[str, Any]):
        """Check for critical drawdown (< -18%)"""
        drawdown = metrics.get('max_drawdown', 0)
        threshold = self.THRESHOLDS['critical']['max_drawdown']

        if drawdown < threshold:
            drawdown_days = metrics.get('drawdown_days', 0)
            self.alerts.append({
                'type': 'critical_drawdown',
                'severity': 'critical',
                'title': 'Max Drawdown Critique',
                'value': f'{drawdown*100:.2f}%',
                'threshold': f'{threshold*100:.1f}%',
                'impact': f'Perte significative sur {drawdown_days} jours',
                'recommendation': 'Revoir allocation, identifier positions perdantes à couper',
                'action_deadline': 'Cette semaine',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    def _check_critical_beta(self, metrics: Dict[str, Any]):
        """Check for extreme beta (> 1.6 or < 0.3)"""
        beta = metrics.get('beta_portfolio', 1.0)
        threshold_high = self.THRESHOLDS['critical']['beta_high']
        threshold_low = self.THRESHOLDS['critical']['beta_low']

        if beta > threshold_high:
            self.alerts.append({
                'type': 'high_beta',
                'severity': 'critical',
                'title': 'Beta Trop Élevé',
                'value': f'{beta:.2f}',
                'threshold': f'> {threshold_high:.1f}',
                'impact': 'Portfolio trop corrélé au marché (haute volatilité)',
                'recommendation': 'Ajouter actifs défensifs ou décorrélés',
                'action_deadline': '1-2 semaines',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })
        elif beta < threshold_low:
            self.alerts.append({
                'type': 'low_beta',
                'severity': 'critical',
                'title': 'Beta Trop Faible',
                'value': f'{beta:.2f}',
                'threshold': f'< {threshold_low:.1f}',
                'impact': 'Portfolio décorrélé du marché (manque opportunités)',
                'recommendation': 'Augmenter exposition indices/ETFs',
                'action_deadline': '1-2 semaines',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    # === WARNING ALERTS ===

    def _check_warning_var(self, metrics: Dict[str, Any]):
        """Check for warning VaR (2.5-4%)"""
        var_95 = abs(metrics.get('var_95_1d', 0))
        min_threshold = self.THRESHOLDS['warning']['var_95_1d_min']
        max_threshold = self.THRESHOLDS['warning']['var_95_1d_max']

        if min_threshold < var_95 <= max_threshold:
            self.alerts.append({
                'type': 'elevated_var',
                'severity': 'warning',
                'title': 'VaR Élevé',
                'value': f'{var_95*100:.2f}%',
                'threshold': f'{min_threshold*100:.1f}-{max_threshold*100:.1f}%',
                'impact': 'Volatilité modérée, surveiller évolution',
                'recommendation': 'Envisager hedging si persistant > 2 semaines',
                'action_deadline': '2-4 semaines',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    def _check_warning_drawdown(self, metrics: Dict[str, Any]):
        """Check for warning drawdown (-12% to -18%)"""
        drawdown = metrics.get('max_drawdown', 0)
        min_threshold = self.THRESHOLDS['warning']['max_drawdown_min']
        max_threshold = self.THRESHOLDS['warning']['max_drawdown_max']

        if min_threshold < drawdown <= max_threshold:
            drawdown_days = metrics.get('drawdown_days', 0)
            self.alerts.append({
                'type': 'elevated_drawdown',
                'severity': 'warning',
                'title': 'Drawdown Modéré',
                'value': f'{drawdown*100:.2f}%',
                'threshold': f'{max_threshold*100:.1f} à {min_threshold*100:.1f}%',
                'impact': f'Perte modérée sur {drawdown_days} jours',
                'recommendation': 'Identifier positions perdantes, préparer rotation',
                'action_deadline': '2-4 semaines',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    def _check_warning_sharpe(self, metrics: Dict[str, Any]):
        """Check for low Sharpe ratio (< 0.8)"""
        sharpe = metrics.get('sharpe_ratio', 0)
        threshold = self.THRESHOLDS['warning']['sharpe_ratio']

        if 0 < sharpe < threshold:
            self.alerts.append({
                'type': 'low_sharpe',
                'severity': 'warning',
                'title': 'Sharpe Ratio Sous-Optimal',
                'value': f'{sharpe:.2f}',
                'threshold': f'< {threshold:.1f}',
                'impact': 'Rendement ajusté au risque faible',
                'recommendation': 'Revoir allocation pour améliorer rendement/risque',
                'action_deadline': '1-2 mois',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    # === SPECIALIZED ALERTS ===

    def _check_margin_alerts(self, specialized_data: Dict[str, Any]):
        """Check margin utilization alerts"""
        margin_data = specialized_data.get('margin', {})
        if not margin_data:
            return

        utilization = margin_data.get('margin_utilization', 0)

        # Skip margin alerts if no leverage (margin_utilization = 0)
        if utilization == 0:
            return

        # Critical: > 85%
        if utilization > self.THRESHOLDS['critical']['margin_utilization']:
            self.alerts.append({
                'type': 'margin_call_risk',
                'severity': 'critical',
                'title': 'Risque Margin Call',
                'value': f'{utilization*100:.1f}%',
                'threshold': f"> {self.THRESHOLDS['critical']['margin_utilization']*100:.0f}%",
                'impact': 'Margin call imminent si marché baisse',
                'recommendation': 'Réduire leverage immédiatement ou déposer fonds',
                'action_deadline': 'Immédiat',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })
        # Warning: 70-85%
        elif (self.THRESHOLDS['warning']['margin_utilization_min'] < utilization
              <= self.THRESHOLDS['warning']['margin_utilization_max']):
            margin_call_distance = margin_data.get('margin_call_distance', 0)
            self.alerts.append({
                'type': 'margin_elevated',
                'severity': 'warning',
                'title': 'Margin Élevé',
                'value': f'{utilization*100:.1f}%',
                'threshold': '70-85%',
                'impact': f'Distance margin call: {margin_call_distance*100:.1f}%',
                'recommendation': 'Réduire leverage progressivement, préparer cash buffer',
                'action_deadline': '1-2 semaines',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    def _check_concentration_alerts(self, specialized_data: Dict[str, Any]):
        """Check concentration alerts (sector, top positions)"""
        sector_data = specialized_data.get('sectors', {})

        # Check sector concentration
        if sector_data:
            for sector_name, sector_info in sector_data.items():
                weight = sector_info.get('weight', 0)
                threshold = self.THRESHOLDS['warning']['concentration_sector']

                if weight > threshold:
                    top_positions = ', '.join(sector_info.get('top_tickers', [])[:3])
                    self.alerts.append({
                        'type': 'sector_concentration',
                        'severity': 'warning',
                        'title': f'Concentration {sector_name} Élevée',
                        'value': f'{weight*100:.1f}%',
                        'threshold': f'> {threshold*100:.0f}%',
                        'impact': f'Risque sectoriel: {top_positions}',
                        'recommendation': f'Diversifier hors {sector_name} sur 2-4 semaines',
                        'action_deadline': '2-4 semaines',
                        'created_at': datetime.utcnow().isoformat() + 'Z'
                    })
                    break  # Only report most concentrated sector

    # === ML/INFO ALERTS ===

    def _check_regime_change_alert(self, ml_data: Dict[str, Any]):
        """Check for regime change with high confidence"""
        regime = ml_data.get('regime', {})
        if not regime:
            return

        current_regime = regime.get('current_regime', '')
        confidence = regime.get('confidence', 0)
        threshold = self.THRESHOLDS['info']['regime_confidence']

        if confidence > threshold and current_regime in ['Bear Market', 'Bull Market']:
            regime_probs = regime.get('regime_probabilities', {})
            self.alerts.append({
                'type': 'regime_change',
                'severity': 'info',
                'title': f'Régime: {current_regime}',
                'value': f'{confidence*100:.0f}% confiance',
                'threshold': f'> {threshold*100:.0f}%',
                'impact': f"Probabilities: {', '.join([f'{k}: {v*100:.0f}%' for k, v in list(regime_probs.items())[:3]])}",
                'recommendation': self._get_regime_recommendation(current_regime),
                'action_deadline': '1-3 mois',
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })

    def _check_volatility_forecast_alert(self, ml_data: Dict[str, Any]):
        """Check for significant volatility increase forecast"""
        vol_forecast = ml_data.get('volatility_forecast', {})
        if not vol_forecast:
            return

        vol_7d = vol_forecast.get('7d', {}).get('predicted_volatility', 0)
        vol_30d = vol_forecast.get('30d', {}).get('predicted_volatility', 0)

        # If 7d vol >> 30d vol (40% increase), turbulence expected
        if vol_30d > 0:
            vol_increase = (vol_7d - vol_30d) / vol_30d
            threshold = self.THRESHOLDS['info']['vol_increase']

            if vol_increase > threshold:
                self.alerts.append({
                    'type': 'high_vol_forecast',
                    'severity': 'info',
                    'title': 'Volatilité Prévue Élevée',
                    'value': f'+{vol_increase*100:.0f}%',
                    'threshold': f'> +{threshold*100:.0f}%',
                    'impact': f'Vol 7j: {vol_7d*100:.1f}% vs 30j: {vol_30d*100:.1f}%',
                    'recommendation': 'Réduire sizing positions temporairement, envisager hedging',
                    'action_deadline': '1-2 semaines',
                    'created_at': datetime.utcnow().isoformat() + 'Z'
                })

    # === HELPERS ===

    def _get_regime_recommendation(self, regime: str) -> str:
        """Get recommendation based on regime"""
        recommendations = {
            'Bull Market': 'Maintenir exposition growth, envisager rotation vers cycliques',
            'Bear Market': 'Réduire exposure growth, augmenter défensifs (healthcare, utilities, bonds)',
            'Consolidation': 'Position neutre, attendre signal directionnel',
            'Distribution': 'Préparer rotation, surveiller sortie distribution'
        }
        return recommendations.get(regime, 'Ajuster allocation selon profil risque')
