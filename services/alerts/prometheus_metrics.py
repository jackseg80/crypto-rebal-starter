"""
Prometheus metrics for Phase 2A Alert System

Provides comprehensive metrics for monitoring alert system performance,
storage degradation, and operational health.
"""

from prometheus_client import Counter, Gauge, Histogram, Enum, Info, CollectorRegistry, REGISTRY
from typing import Dict, Any, List
import time
from datetime import datetime


class AlertPrometheusMetrics:
    """Prometheus metrics collector for Alert System"""
    
    def __init__(self, registry=None):
        if registry is None:
            registry = REGISTRY
        # Alert generation metrics
        self.alerts_total = Counter(
            'crypto_rebal_alerts_generated_total',
            'Total number of alerts generated',
            ['alert_type', 'severity', 'source'],
            registry=registry
        )
        
        self.alerts_acknowledged_total = Counter(
            'crypto_rebal_alerts_acknowledged_total', 
            'Total number of alerts acknowledged',
            ['alert_type', 'severity']
        )
        
        self.alerts_snoozed_total = Counter(
            'crypto_rebal_alerts_snoozed_total',
            'Total number of alerts snoozed',
            ['alert_type', 'severity']
        )
        
        self.alerts_applied_total = Counter(
            'crypto_rebal_alerts_applied_total',
            'Total number of alert actions applied',
            ['alert_type', 'action_type']
        )
        
        # Alert state gauges
        self.alerts_active = Gauge(
            'crypto_rebal_alerts_active',
            'Number of currently active alerts',
            ['severity']
        )
        
        self.alerts_snoozed = Gauge(
            'crypto_rebal_alerts_snoozed',
            'Number of currently snoozed alerts'
        )
        
        # Escalation metrics
        self.escalations_total = Counter(
            'crypto_rebal_alert_escalations_total',
            'Total number of alert escalations',
            ['from_severity', 'to_severity', 'alert_type']
        )
        
        self.escalation_time = Histogram(
            'crypto_rebal_alert_escalation_time_seconds',
            'Time between first alert and escalation',
            ['alert_type'],
            buckets=[30, 60, 300, 600, 1800, 3600]  # 30s to 1h
        )
        
        # Storage performance metrics
        self.storage_operations_total = Counter(
            'crypto_rebal_alert_storage_operations_total',
            'Total storage operations',
            ['operation', 'storage_mode', 'result']
        )
        
        self.storage_operation_duration = Histogram(
            'crypto_rebal_alert_storage_operation_duration_seconds',
            'Duration of storage operations',
            ['operation', 'storage_mode'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )
        
        # Phase 2A: Storage mode and degradation
        self.storage_mode = Enum(
            'crypto_rebal_alert_storage_mode',
            'Current alert storage mode',
            states=['redis', 'file', 'in_memory']
        )
        
        self.storage_degraded = Gauge(
            'crypto_rebal_alert_storage_degraded',
            'Whether alert storage is in degraded mode (1=degraded, 0=normal)'
        )
        
        self.redis_failures_total = Counter(
            'crypto_rebal_alert_redis_failures_total',
            'Total Redis operation failures',
            ['operation_type']
        )
        
        self.file_failures_total = Counter(
            'crypto_rebal_alert_file_failures_total',
            'Total file operation failures',
            ['operation_type']
        )
        
        self.memory_alerts = Gauge(
            'crypto_rebal_alert_memory_storage_count',
            'Number of alerts stored in degraded memory mode'
        )
        
        # Lua script performance (Phase 2A)
        self.lua_script_executions_total = Counter(
            'crypto_rebal_alert_lua_executions_total',
            'Total Lua script executions',
            ['script_name', 'result']
        )
        
        self.lua_script_duration = Histogram(
            'crypto_rebal_alert_lua_duration_seconds',
            'Lua script execution duration',
            ['script_name'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
        )
        
        # Rate limiting metrics
        self.rate_limit_hits_total = Counter(
            'crypto_rebal_alert_rate_limit_hits_total',
            'Total rate limit hits',
            ['alert_type', 'severity']
        )
        
        self.rate_limit_budget_remaining = Gauge(
            'crypto_rebal_alert_rate_limit_budget_remaining',
            'Remaining rate limit budget',
            ['alert_type', 'severity', 'window']
        )
        
        # Alert Engine health
        self.engine_last_run = Gauge(
            'crypto_rebal_alert_engine_last_run_timestamp',
            'Timestamp of last alert engine run'
        )
        
        self.engine_evaluation_duration = Histogram(
            'crypto_rebal_alert_engine_evaluation_duration_seconds',
            'Duration of alert evaluation cycles',
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        self.governance_signals_processed = Counter(
            'crypto_rebal_alert_governance_signals_processed_total',
            'Total governance signals processed',
            ['signal_type']
        )
        
        # ML Signal quality metrics
        self.ml_signal_quality = Gauge(
            'crypto_rebal_alert_ml_signal_quality',
            'ML signal quality score',
            ['signal_type']
        )
        
        self.ml_contradiction_index = Gauge(
            'crypto_rebal_alert_ml_contradiction_index',
            'Current ML contradiction index'
        )
        
        self.ml_confidence_score = Gauge(
            'crypto_rebal_alert_ml_confidence_score',
            'Current ML confidence score'
        )
        
        # Phase 2A: Phase-aware metrics
        self.phase_aware_enabled = Gauge(
            'crypto_rebal_alert_phase_aware_enabled',
            'Whether phase-aware alerting is enabled (1=enabled, 0=disabled)'
        )
        
        self.current_lagged_phase = Enum(
            'crypto_rebal_alert_current_lagged_phase',
            'Current lagged phase for alert evaluation',
            states=['btc', 'eth', 'large', 'alt', 'unknown']
        )
        
        self.phase_lag_minutes = Gauge(
            'crypto_rebal_alert_phase_lag_minutes',
            'Configured phase lag in minutes'
        )
        
        self.phase_persistence_count = Gauge(
            'crypto_rebal_alert_phase_persistence_count',
            'Current phase persistence count'
        )
        
        self.phase_persistence_required = Gauge(
            'crypto_rebal_alert_phase_persistence_required',
            'Required phase persistence ticks'
        )
        
        self.alerts_neutralized_total = Counter(
            'crypto_rebal_alerts_neutralized_total',
            'Total alerts neutralized by phase-aware guards',
            ['reason', 'alert_type']
        )
        
        self.phase_transitions_total = Counter(
            'crypto_rebal_alert_phase_transitions_total',
            'Total phase transitions detected',
            ['from_phase', 'to_phase']
        )
        
        self.gating_matrix_blocks_total = Counter(
            'crypto_rebal_alert_gating_matrix_blocks_total',
            'Total alerts blocked by gating matrix',
            ['phase', 'alert_type', 'action']
        )
        
        self.adaptive_threshold_adjustments_total = Counter(
            'crypto_rebal_alert_adaptive_threshold_adjustments_total',
            'Total adaptive threshold adjustments applied',
            ['alert_type', 'phase']
        )
        
        self.contradiction_neutralizations_total = Counter(
            'crypto_rebal_alert_contradiction_neutralizations_total',
            'Total alerts neutralized due to high contradiction index',
            ['alert_type']
        )
        
        # System info
        self.system_info = Info(
            'crypto_rebal_alert_system_info',
            'Alert system version and configuration info'
        )
        
        # Configuration hot-reload metrics
        self.config_reloads_total = Counter(
            'crypto_rebal_alert_config_reloads_total',
            'Total configuration reloads',
            ['result']
        )
        
        self.config_version = Info(
            'crypto_rebal_alert_config_version',
            'Current alert configuration version'
        )
        
        # Phase 2B1: Multi-Timeframe Analysis Metrics
        self.multi_timeframe_enabled = Gauge(
            'crypto_rebal_alert_multi_timeframe_enabled',
            'Multi-timeframe analysis enabled status'
        )
        
        self.multi_timeframe_signals_total = Counter(
            'crypto_rebal_alert_multi_timeframe_signals_total',
            'Total signals processed by timeframe',
            ['timeframe', 'alert_type', 'severity']
        )
        
        self.multi_timeframe_coherence_scores = Histogram(
            'crypto_rebal_alert_multi_timeframe_coherence_scores',
            'Distribution of coherence scores by alert type',
            ['alert_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.multi_timeframe_alerts_suppressed_total = Counter(
            'crypto_rebal_alert_multi_timeframe_suppressed_total',
            'Alerts suppressed by multi-timeframe analysis',
            ['reason', 'alert_type', 'coherence_level']
        )
        
        self.multi_timeframe_alerts_triggered_total = Counter(
            'crypto_rebal_alert_multi_timeframe_triggered_total',
            'Alerts triggered by multi-timeframe analysis',
            ['reason', 'alert_type', 'coherence_level']
        )
        
        self.temporal_gating_blocks_total = Counter(
            'crypto_rebal_alert_temporal_gating_blocks_total',
            'Total alerts blocked by temporal gating',
            ['timeframe', 'alert_type', 'gating_action']
        )
        
        self.timeframe_divergences_detected_total = Counter(
            'crypto_rebal_alert_timeframe_divergences_total',
            'Total timeframe divergences detected',
            ['alert_type', 'conflicting_timeframes']
        )
        
        self.timeframe_agreement_ratio = Gauge(
            'crypto_rebal_alert_timeframe_agreement_ratio',
            'Current timeframe agreement ratio by alert type',
            ['alert_type']
        )
        
        self.dominant_timeframe_changes_total = Counter(
            'crypto_rebal_alert_dominant_timeframe_changes_total',
            'Total dominant timeframe changes',
            ['alert_type', 'from_timeframe', 'to_timeframe']
        )
        
        # Phase 2B2: Cross-Asset Correlation Metrics
        self.correlation_spikes_total = Counter(
            'crypto_rebal_alert_correlation_spikes_total',
            'Total correlation spikes detected',
            ['asset_pair', 'severity', 'timeframe']
        )
        
        self.systemic_risk_score = Gauge(
            'crypto_rebal_alert_systemic_risk_score',
            'Current systemic risk score (0-1)'
        )
        
        self.correlation_matrix_values = Histogram(
            'crypto_rebal_alert_correlation_matrix_values',
            'Distribution of correlation matrix values',
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.concentration_clusters_detected = Gauge(
            'crypto_rebal_alert_concentration_clusters_detected',
            'Number of concentration clusters detected'
        )
    
    def record_alert_generated(self, alert_type: str, severity: str, source: str = "ml_signals"):
        """Record an alert generation"""
        self.alerts_total.labels(
            alert_type=alert_type,
            severity=severity,
            source=source
        ).inc()
    
    def record_alert_acknowledged(self, alert_type: str, severity: str):
        """Record an alert acknowledgment"""
        self.alerts_acknowledged_total.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
    
    def record_alert_snoozed(self, alert_type: str, severity: str):
        """Record an alert snooze"""
        self.alerts_snoozed_total.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
    
    def record_alert_action_applied(self, alert_type: str, action_type: str):
        """Record an alert action application"""
        self.alerts_applied_total.labels(
            alert_type=alert_type,
            action_type=action_type
        ).inc()
    
    def record_escalation(self, from_severity: str, to_severity: str, alert_type: str, 
                         escalation_time_seconds: float):
        """Record an alert escalation"""
        self.escalations_total.labels(
            from_severity=from_severity,
            to_severity=to_severity,
            alert_type=alert_type
        ).inc()
        
        self.escalation_time.labels(alert_type=alert_type).observe(escalation_time_seconds)
    
    def record_storage_operation(self, operation: str, storage_mode: str, 
                               result: str, duration_seconds: float):
        """Record a storage operation"""
        self.storage_operations_total.labels(
            operation=operation,
            storage_mode=storage_mode,
            result=result
        ).inc()
        
        self.storage_operation_duration.labels(
            operation=operation,
            storage_mode=storage_mode
        ).observe(duration_seconds)
    
    def record_lua_script_execution(self, script_name: str, result: str, duration_seconds: float):
        """Record Lua script execution"""
        self.lua_script_executions_total.labels(
            script_name=script_name,
            result=result
        ).inc()
        
        self.lua_script_duration.labels(script_name=script_name).observe(duration_seconds)
    
    def record_rate_limit_hit(self, alert_type: str, severity: str):
        """Record a rate limit hit"""
        self.rate_limit_hits_total.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
    
    def update_storage_metrics(self, storage_metrics: Dict[str, Any]):
        """Update storage-related metrics from AlertStorage.get_metrics()"""
        # Storage mode
        current_mode = storage_metrics.get('storage_mode', 'unknown')
        if current_mode in ['redis', 'file', 'in_memory']:
            self.storage_mode.state(current_mode)
        
        # Degradation status
        is_degraded = storage_metrics.get('is_degraded', False)
        self.storage_degraded.set(1 if is_degraded else 0)
        
        # Failure counts
        redis_failures = storage_metrics.get('redis_failures', 0)
        file_failures = storage_metrics.get('file_failures', 0)
        
        # Update counters (only increment by difference)
        if hasattr(self, '_last_redis_failures'):
            redis_diff = redis_failures - self._last_redis_failures
            if redis_diff > 0:
                self.redis_failures_total.labels(operation_type='general')._value._value += redis_diff
        self._last_redis_failures = redis_failures
        
        if hasattr(self, '_last_file_failures'):
            file_diff = file_failures - self._last_file_failures
            if file_diff > 0:
                self.file_failures_total.labels(operation_type='general')._value._value += file_diff
        self._last_file_failures = file_failures
        
        # Memory storage count
        memory_count = storage_metrics.get('memory_alerts_count', 0)
        self.memory_alerts.set(memory_count)
    
    def update_alert_counts(self, alert_counts: Dict[str, int]):
        """Update active alert counts"""
        # Update active alerts by severity
        for severity in ['S1', 'S2', 'S3']:
            count = alert_counts.get(f'active_{severity.lower()}', 0)
            self.alerts_active.labels(severity=severity).set(count)
        
        # Update snoozed alerts
        snoozed_count = alert_counts.get('snoozed', 0)
        self.alerts_snoozed.set(snoozed_count)
    
    def update_ml_signals(self, signals: Dict[str, Any]):
        """Update ML signal quality metrics"""
        if 'contradiction_index' in signals:
            self.ml_contradiction_index.set(signals['contradiction_index'])
        
        if 'confidence' in signals:
            self.ml_confidence_score.set(signals['confidence'])
        
        # Update signal quality for different signal types
        if 'volatility' in signals:
            # Calculate volatility quality (example: inverse of variance)
            vol_values = list(signals['volatility'].values()) if isinstance(signals['volatility'], dict) else [signals['volatility']]
            if vol_values:
                vol_quality = 1.0 - (max(vol_values) - min(vol_values)) if len(vol_values) > 1 else 1.0
                self.ml_signal_quality.labels(signal_type='volatility').set(vol_quality)
    
    def record_engine_run(self, duration_seconds: float):
        """Record alert engine evaluation run"""
        self.engine_last_run.set(time.time())
        self.engine_evaluation_duration.observe(duration_seconds)
    
    def record_governance_signal(self, signal_type: str):
        """Record governance signal processing"""
        self.governance_signals_processed.labels(signal_type=signal_type).inc()
    
    def record_config_reload(self, result: str, config_version: str = None):
        """Record configuration reload"""
        self.config_reloads_total.labels(result=result).inc()
        
        if config_version:
            self.config_version.info({
                'version': config_version,
                'reloaded_at': datetime.now().isoformat()
            })
    
    def set_system_info(self, version: str, phase: str, features: Dict[str, str]):
        """Set system information"""
        info_dict = {
            'version': version,
            'phase': phase,
            **features
        }
        self.system_info.info(info_dict)
    
    # Phase 2A: Phase-aware metrics methods
    def update_phase_aware_config(self, enabled: bool, lag_minutes: int, persistence_ticks: int):
        """Update phase-aware configuration metrics"""
        self.phase_aware_enabled.set(1 if enabled else 0)
        self.phase_lag_minutes.set(lag_minutes)
        self.phase_persistence_required.set(persistence_ticks)
    
    def update_current_lagged_phase(self, phase: str, persistence_count: int = 0):
        """Update current lagged phase and persistence"""
        if phase in ['btc', 'eth', 'large', 'alt']:
            self.current_lagged_phase.state(phase)
        else:
            self.current_lagged_phase.state('unknown')
        self.phase_persistence_count.set(persistence_count)
    
    def record_alert_neutralized(self, reason: str, alert_type: str):
        """Record an alert neutralization by phase-aware guards"""
        self.alerts_neutralized_total.labels(
            reason=reason,
            alert_type=alert_type
        ).inc()
    
    def record_phase_transition(self, from_phase: str, to_phase: str):
        """Record a phase transition"""
        self.phase_transitions_total.labels(
            from_phase=from_phase,
            to_phase=to_phase
        ).inc()
    
    def record_gating_matrix_block(self, phase: str, alert_type: str, action: str):
        """Record an alert blocked by gating matrix"""
        self.gating_matrix_blocks_total.labels(
            phase=phase,
            alert_type=alert_type,
            action=action
        ).inc()
    
    # Phase 2B1: Multi-Timeframe Metrics Methods
    def update_multi_timeframe_config(self, enabled: bool):
        """Update multi-timeframe enabled status"""
        self.multi_timeframe_enabled.set(1 if enabled else 0)
    
    def record_multi_timeframe_signal(self, timeframe: str, alert_type: str, severity: str):
        """Record a signal processed by timeframe"""
        self.multi_timeframe_signals_total.labels(
            timeframe=timeframe,
            alert_type=alert_type,
            severity=severity
        ).inc()
    
    def record_coherence_score(self, alert_type: str, coherence_score: float):
        """Record coherence score distribution"""
        self.multi_timeframe_coherence_scores.labels(
            alert_type=alert_type
        ).observe(coherence_score)
    
    def record_multi_timeframe_suppression(self, reason: str, alert_type: str, coherence_level: str):
        """Record alert suppressed by multi-timeframe analysis"""
        self.multi_timeframe_alerts_suppressed_total.labels(
            reason=reason,
            alert_type=alert_type,
            coherence_level=coherence_level
        ).inc()
    
    def record_multi_timeframe_trigger(self, reason: str, alert_type: str, coherence_level: str):
        """Record alert triggered by multi-timeframe analysis"""
        self.multi_timeframe_alerts_triggered_total.labels(
            reason=reason,
            alert_type=alert_type,
            coherence_level=coherence_level
        ).inc()
    
    def record_temporal_gating_block(self, timeframe: str, alert_type: str, gating_action: str):
        """Record alert blocked by temporal gating"""
        self.temporal_gating_blocks_total.labels(
            timeframe=timeframe,
            alert_type=alert_type,
            gating_action=gating_action
        ).inc()
    
    def record_timeframe_divergence(self, alert_type: str, conflicting_timeframes: str):
        """Record timeframe divergence detection"""
        self.timeframe_divergences_detected_total.labels(
            alert_type=alert_type,
            conflicting_timeframes=conflicting_timeframes
        ).inc()
    
    def update_timeframe_agreement_ratio(self, alert_type: str, agreement_ratio: float):
        """Update current timeframe agreement ratio"""
        self.timeframe_agreement_ratio.labels(
            alert_type=alert_type
        ).set(agreement_ratio)
    
    def record_dominant_timeframe_change(self, alert_type: str, from_timeframe: str, to_timeframe: str):
        """Record dominant timeframe change"""
        self.dominant_timeframe_changes_total.labels(
            alert_type=alert_type,
            from_timeframe=from_timeframe,
            to_timeframe=to_timeframe
        ).inc()
    
    def record_adaptive_threshold_adjustment(self, alert_type: str, phase: str):
        """Record an adaptive threshold adjustment"""
        self.adaptive_threshold_adjustments_total.labels(
            alert_type=alert_type,
            phase=phase
        ).inc()
    
    def record_contradiction_neutralization(self, alert_type: str):
        """Record an alert neutralized due to high contradiction index"""
        self.contradiction_neutralizations_total.labels(
            alert_type=alert_type
        ).inc()
    
    # Phase 2B2: Cross-Asset Correlation Metrics Methods
    def record_correlation_spike(self, asset_pair: str, severity: str, absolute_change: float, timeframe: str):
        """Record a correlation spike detection"""
        self.correlation_spikes_total.labels(
            asset_pair=asset_pair,
            severity=severity,
            timeframe=timeframe
        ).inc()
    
    def update_systemic_risk_score(self, score: float):
        """Update systemic risk score gauge"""
        self.systemic_risk_score.set(score)
    
    def record_concentration_cluster(self, cluster_size: int, risk_score: float):
        """Record concentration cluster detection"""
        self.concentration_clusters_detected.set(1)  # At least one cluster detected
        
    def update_correlation_matrix_values(self, correlation_values: List[float]):
        """Update correlation matrix values distribution"""
        for value in correlation_values:
            self.correlation_matrix_values.observe(abs(value))
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics for debugging"""
        return {
            'alerts_total': {
                family.name: {str(sample.labels): sample.value 
                            for sample in family.samples}
                for family in [self.alerts_total._value]
            },
            'storage_mode': getattr(self.storage_mode._value, '_value', 'unknown'),
            'degraded': bool(self.storage_degraded._value._value),
            'memory_alerts': self.memory_alerts._value._value,
            'last_engine_run': self.engine_last_run._value._value,
        }


class AlertPrometheusStub:
    """Stub implementation when metrics are already registered elsewhere"""
    
    def record_alert_generated(self, alert_type: str, severity: str, source: str = "ml_signals"):
        pass  # No-op
    
    def record_alert_acknowledged(self, alert_type: str, severity: str):
        pass
    
    def record_alert_snoozed(self, alert_type: str, severity: str):
        pass
    
    def record_alert_action_applied(self, alert_type: str, action_type: str):
        pass
    
    def record_escalation(self, from_severity: str, to_severity: str, alert_type: str, 
                         escalation_time_seconds: float):
        pass
    
    def record_storage_operation(self, operation: str, storage_mode: str, 
                               result: str, duration_seconds: float):
        pass
    
    def record_lua_script_execution(self, script_name: str, result: str, duration_seconds: float):
        pass
    
    def record_rate_limit_hit(self, alert_type: str, severity: str):
        pass
    
    def update_storage_metrics(self, storage_metrics: Dict[str, Any]):
        pass
    
    def update_alert_counts(self, alert_counts: Dict[str, int]):
        pass
    
    def update_ml_signals(self, signals: Dict[str, Any]):
        pass
    
    def record_engine_run(self, duration_seconds: float):
        pass
    
    def record_governance_signal(self, signal_type: str):
        pass
    
    def record_config_reload(self, result: str, config_version: str = None):
        pass
    
    def set_system_info(self, version: str, phase: str, features: Dict[str, str]):
        pass
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        return {"stub": True, "message": "Metrics already registered elsewhere"}
    
    # Phase 2A: Stub methods for phase-aware metrics
    def update_phase_aware_config(self, enabled: bool, lag_minutes: int, persistence_ticks: int):
        pass
    
    def update_current_lagged_phase(self, phase: str, persistence_count: int = 0):
        pass
    
    def record_alert_neutralized(self, reason: str, alert_type: str):
        pass
    
    def record_phase_transition(self, from_phase: str, to_phase: str):
        pass
    
    def record_gating_matrix_block(self, phase: str, alert_type: str, action: str):
        pass
    
    def record_adaptive_threshold_adjustment(self, alert_type: str, phase: str):
        pass
    
    def record_contradiction_neutralization(self, alert_type: str):
        pass
    
    # Phase 2B1: Stub methods for multi-timeframe metrics
    def update_multi_timeframe_config(self, enabled: bool):
        pass
    
    def record_coherence_score(self, alert_type: str, score: float):
        pass
    
    def record_multi_timeframe_alert_suppression(self, alert_type: str, reason: str):
        pass
    
    def record_temporal_gating_block(self, alert_type: str, timeframe: str, reason: str):
        pass
    
    def record_timeframe_signal_count(self, timeframe: str, count: int):
        pass
    
    def record_multi_timeframe_decision(self, alert_type: str, decision: str, confidence_adjustment: float):
        pass
    
    def record_multi_timeframe_trigger(self, reason: str, alert_type: str, coherence_level: str):
        pass
    
    def update_timeframe_agreement_ratio(self, alert_type: str, agreement_ratio: float):
        pass
    
    # Phase 2B2: Stub methods for cross-asset correlation metrics
    def record_correlation_spike(self, asset_pair: str, severity: str, absolute_change: float, timeframe: str):
        pass
    
    def update_systemic_risk_score(self, score: float):
        pass
    
    def record_concentration_cluster(self, cluster_size: int, risk_score: float):
        pass
        
    def update_correlation_matrix_values(self, correlation_values: List[float]):
        pass


# Global instance - will be initialized on first import
alert_metrics = None

def get_alert_metrics(registry=None):
    """Get or create alert metrics instance"""
    global alert_metrics
    if registry is not None:
        # Create new instance for tests with custom registry
        return AlertPrometheusMetrics(registry=registry)
    
    # For global registry, reuse existing instance to avoid conflicts
    if alert_metrics is None:
        try:
            alert_metrics = AlertPrometheusMetrics()
        except ValueError as e:
            if "Duplicated timeseries" in str(e):
                # Metrics already exist, create a stub that doesn't register new ones
                alert_metrics = AlertPrometheusStub()
            else:
                raise
    return alert_metrics

# Initialize system info when metrics are first accessed
def _initialize_system_info():
    """Initialize system info for alert metrics"""
    metrics = get_alert_metrics()
    metrics.set_system_info(
        version="2.0.0",
        phase="2A", 
        features={
            "redis_zset_hash": "true",
            "lua_atomic_scripts": "true", 
            "fallback_cascade": "true",
            "ui_toasts": "true",
            "modal_views": "true",
            "prometheus_metrics": "true"
        }
    )