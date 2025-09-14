"""
Performance benchmarks for Phase 2A - Phase-Aware Alerting System

Measures performance impact and scalability of Phase 2A components:
- Phase lagging and persistence calculations
- Gating matrix lookups
- Adaptive threshold calculations 
- Metrics recording overhead
- Memory usage and cleanup
"""

import pytest
import time
import psutil
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from statistics import mean, stdev
from typing import List, Dict, Any

from services.alerts.alert_engine import AlertEngine, PhaseSnapshot, PhaseAwareContext
from services.alerts.alert_types import AlertType, AlertEvaluator
from services.execution.phase_engine import Phase
from services.alerts.prometheus_metrics import get_alert_metrics


class TestPhaseAwarePerformance:
    """Performance benchmarks for Phase 2A components"""
    
    @pytest.fixture
    def perf_config(self):
        """Performance test configuration"""
        return {
            "metadata": {
                "config_version": "perf-test-2A.0",
                "last_updated": datetime.now(timezone.utc).isoformat()
            },
            "alerting_config": {
                "phase_aware": {
                    "enabled": True,
                    "phase_lag_minutes": 15,
                    "phase_persistence_ticks": 3,
                    "contradiction_neutralize_threshold": 0.70,
                    "phase_factors": {
                        "VOL_Q90_CROSS": {
                            "btc": 1.0, "eth": 1.1, "large": 1.2, "alt": 1.3
                        },
                        "CONTRADICTION_SPIKE": {
                            "btc": 1.0, "eth": 1.0, "large": 1.1, "alt": 1.2
                        },
                        "REGIME_FLIP": {
                            "btc": 0.9, "eth": 1.0, "large": 1.1, "alt": 1.2
                        },
                        "CORR_HIGH": {
                            "btc": 1.0, "eth": 0.95, "large": 1.05, "alt": 1.15
                        },
                        "DECISION_DROP": {
                            "btc": 0.8, "eth": 0.9, "large": 1.0, "alt": 1.3
                        },
                        "EXEC_COST_SPIKE": {
                            "btc": 0.9, "eth": 1.0, "large": 1.1, "alt": 1.4
                        }
                    },
                    "gating_matrix": {
                        "btc": {
                            "VOL_Q90_CROSS": "enabled",
                            "CONTRADICTION_SPIKE": "enabled",
                            "REGIME_FLIP": "enabled",
                            "CORR_HIGH": "enabled",
                            "DECISION_DROP": "enabled",
                            "EXEC_COST_SPIKE": "enabled"
                        },
                        "eth": {
                            "VOL_Q90_CROSS": "enabled",
                            "CONTRADICTION_SPIKE": "attenuated",
                            "REGIME_FLIP": "enabled",
                            "CORR_HIGH": "attenuated",
                            "DECISION_DROP": "enabled",
                            "EXEC_COST_SPIKE": "attenuated"
                        },
                        "large": {
                            "VOL_Q90_CROSS": "attenuated",
                            "CONTRADICTION_SPIKE": "attenuated",
                            "REGIME_FLIP": "attenuated",
                            "CORR_HIGH": "attenuated",
                            "DECISION_DROP": "attenuated",
                            "EXEC_COST_SPIKE": "attenuated"
                        },
                        "alt": {
                            "VOL_Q90_CROSS": "disabled",
                            "CONTRADICTION_SPIKE": "disabled",
                            "REGIME_FLIP": "disabled",
                            "CORR_HIGH": "disabled",
                            "DECISION_DROP": "attenuated",
                            "EXEC_COST_SPIKE": "disabled"
                        }
                    }
                }
            }
        }
    
    @pytest.fixture
    def alert_engine(self, perf_config):
        """Create AlertEngine for performance testing"""
        governance_engine = Mock()
        governance_engine.get_ml_signals.return_value = {
            "volatility": {"BTC": 0.15, "ETH": 0.18, "SOL": 0.25, "AVAX": 0.22},
            "correlation": {"avg_correlation": 0.6},
            "confidence": 0.8,
            "contradiction_index": 0.3
        }
        
        with patch('services.alerts.prometheus_metrics.get_alert_metrics') as mock_metrics:
            mock_metrics.return_value = Mock()
            
            engine = AlertEngine(
                governance_engine=governance_engine,
                config=perf_config
            )
            return engine
    
    def benchmark_phase_history_management(self, alert_engine, num_snapshots: int = 1000):
        """Benchmark phase history management with large datasets"""
        context = alert_engine.phase_context
        
        # Generate large phase history
        now = datetime.utcnow()
        phases = [Phase.BTC, Phase.ETH, Phase.LARGE, Phase.ALT]
        
        # Measure time to add snapshots
        start_time = time.perf_counter()
        
        for i in range(num_snapshots):
            phase_state = Mock()
            phase_state.phase_now = phases[i % 4]
            phase_state.confidence = 0.8
            phase_state.persistence_count = (i % 5) + 1
            
            context.update_phase(phase_state, contradiction_index=0.2 + (i % 50) / 100)
        
        update_time = time.perf_counter() - start_time
        
        # Measure memory usage
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        # Measure history cleanup performance
        cleanup_start = time.perf_counter()
        original_size = len(context.phase_history)
        
        # Force cleanup by updating with very recent timestamp
        phase_state = Mock()
        phase_state.phase_now = Phase.BTC
        phase_state.confidence = 0.8
        phase_state.persistence_count = 3
        context.update_phase(phase_state)
        
        cleanup_time = time.perf_counter() - cleanup_start
        cleaned_size = len(context.phase_history)
        
        return {
            "num_snapshots": num_snapshots,
            "update_time_ms": update_time * 1000,
            "update_rate_per_sec": num_snapshots / update_time,
            "memory_mb": memory_mb,
            "original_history_size": original_size,
            "cleaned_history_size": cleaned_size,
            "cleanup_time_ms": cleanup_time * 1000,
            "avg_update_time_us": (update_time / num_snapshots) * 1_000_000
        }
    
    def benchmark_gating_matrix_lookups(self, alert_engine, num_lookups: int = 10000):
        """Benchmark gating matrix lookup performance"""
        phases = [Phase.BTC, Phase.ETH, Phase.LARGE, Phase.ALT]
        alert_types = list(AlertType)
        
        # Setup phase context
        context = alert_engine.phase_context
        
        signals = {
            "volatility": {"BTC": 0.25},
            "contradiction_index": 0.3
        }
        
        # Warm up
        for _ in range(100):
            context.current_lagged_phase = PhaseSnapshot(
                phase=phases[0],
                confidence=0.8,
                persistence_count=3,
                captured_at=datetime.utcnow() - timedelta(minutes=20),
                contradiction_index=0.2
            )
            alert_engine._check_phase_gating(alert_types[0], signals)
        
        # Benchmark
        lookup_times = []
        
        for i in range(num_lookups):
            phase_idx = i % len(phases)
            alert_idx = i % len(alert_types)
            
            context.current_lagged_phase = PhaseSnapshot(
                phase=phases[phase_idx],
                confidence=0.8,
                persistence_count=3,
                captured_at=datetime.utcnow() - timedelta(minutes=20),
                contradiction_index=0.2 + (i % 50) / 100
            )
            
            start = time.perf_counter()
            allowed, reason = alert_engine._check_phase_gating(alert_types[alert_idx], signals)
            lookup_time = time.perf_counter() - start
            
            lookup_times.append(lookup_time)
        
        return {
            "num_lookups": num_lookups,
            "total_time_ms": sum(lookup_times) * 1000,
            "avg_lookup_time_us": mean(lookup_times) * 1_000_000,
            "median_lookup_time_us": sorted(lookup_times)[num_lookups // 2] * 1_000_000,
            "p95_lookup_time_us": sorted(lookup_times)[int(num_lookups * 0.95)] * 1_000_000,
            "p99_lookup_time_us": sorted(lookup_times)[int(num_lookups * 0.99)] * 1_000_000,
            "lookup_rate_per_sec": num_lookups / sum(lookup_times),
            "std_dev_us": stdev(lookup_times) * 1_000_000 if len(lookup_times) > 1 else 0
        }
    
    def benchmark_adaptive_threshold_calculation(self, alert_engine, num_calculations: int = 5000):
        """Benchmark adaptive threshold calculation performance"""
        evaluator = alert_engine.evaluator
        phases = [Phase.BTC, Phase.ETH, Phase.LARGE, Phase.ALT]
        alert_types = list(AlertType)
        
        # Create test rule
        from services.alerts.alert_types import AlertRule
        rule = AlertRule(
            alert_type=AlertType.VOL_Q90_CROSS,
            base_threshold=0.75,
            adaptive_multiplier=1.0,
            hysteresis_minutes=5,
            severity_thresholds={"S1": 0.80, "S2": 0.85, "S3": 0.90},
            suggested_actions={"S1": {"type": "acknowledge"}}
        )
        
        signals = {
            "volatility": {"BTC": 0.25, "ETH": 0.18, "SOL": 0.30},
            "correlation": {"avg_correlation": 0.65},
            "confidence": 0.8
        }
        
        # Warm up
        for _ in range(100):
            phase_context = {
                "phase": phases[0],
                "phase_factors": alert_engine.config["alerting_config"]["phase_aware"]["phase_factors"],
                "contradiction_index": 0.3
            }
            evaluator._calculate_adaptive_threshold(rule, signals, phase_context)
        
        # Benchmark
        calc_times = []
        
        for i in range(num_calculations):
            phase_idx = i % len(phases)
            
            phase_context = {
                "phase": phases[phase_idx],
                "phase_factors": alert_engine.config["alerting_config"]["phase_aware"]["phase_factors"],
                "contradiction_index": 0.2 + (i % 50) / 100
            }
            
            # Vary signals slightly
            test_signals = {
                **signals,
                "confidence": 0.6 + (i % 40) / 100,
                "volatility": {"BTC": 0.20 + (i % 20) / 100}
            }
            
            start = time.perf_counter()
            threshold = evaluator._calculate_adaptive_threshold(rule, test_signals, phase_context)
            calc_time = time.perf_counter() - start
            
            calc_times.append(calc_time)
        
        return {
            "num_calculations": num_calculations,
            "total_time_ms": sum(calc_times) * 1000,
            "avg_calc_time_us": mean(calc_times) * 1_000_000,
            "median_calc_time_us": sorted(calc_times)[num_calculations // 2] * 1_000_000,
            "p95_calc_time_us": sorted(calc_times)[int(num_calculations * 0.95)] * 1_000_000,
            "p99_calc_time_us": sorted(calc_times)[int(num_calculations * 0.99)] * 1_000_000,
            "calc_rate_per_sec": num_calculations / sum(calc_times),
            "std_dev_us": stdev(calc_times) * 1_000_000 if len(calc_times) > 1 else 0
        }
    
    def benchmark_metrics_recording(self, alert_engine, num_metrics: int = 10000):
        """Benchmark Prometheus metrics recording performance"""
        metrics = alert_engine.prometheus_metrics
        phases = ["btc", "eth", "large", "alt"]
        alert_types = [t.value for t in AlertType]
        
        # Warm up
        for _ in range(100):
            metrics.record_phase_transition("btc", "eth")
            metrics.record_gating_matrix_block("btc", "VOL_Q90_CROSS", "enabled")
            metrics.record_contradiction_neutralization("VOL_Q90_CROSS")
            metrics.record_adaptive_threshold_adjustment("VOL_Q90_CROSS", "eth")
        
        # Benchmark different metric types
        results = {}
        
        # Phase transitions
        start = time.perf_counter()
        for i in range(num_metrics // 4):
            from_phase = phases[i % 4]
            to_phase = phases[(i + 1) % 4]
            metrics.record_phase_transition(from_phase, to_phase)
        transition_time = time.perf_counter() - start
        
        # Gating matrix blocks
        start = time.perf_counter()
        for i in range(num_metrics // 4):
            phase = phases[i % 4]
            alert_type = alert_types[i % len(alert_types)]
            action = ["enabled", "disabled", "attenuated"][i % 3]
            metrics.record_gating_matrix_block(phase, alert_type, action)
        gating_time = time.perf_counter() - start
        
        # Contradiction neutralizations
        start = time.perf_counter()
        for i in range(num_metrics // 4):
            alert_type = alert_types[i % len(alert_types)]
            metrics.record_contradiction_neutralization(alert_type)
        contradiction_time = time.perf_counter() - start
        
        # Adaptive threshold adjustments
        start = time.perf_counter()
        for i in range(num_metrics // 4):
            alert_type = alert_types[i % len(alert_types)]
            phase = phases[i % 4]
            metrics.record_adaptive_threshold_adjustment(alert_type, phase)
        threshold_time = time.perf_counter() - start
        
        total_time = transition_time + gating_time + contradiction_time + threshold_time
        
        return {
            "num_metrics": num_metrics,
            "total_time_ms": total_time * 1000,
            "avg_metric_time_us": (total_time / num_metrics) * 1_000_000,
            "metrics_rate_per_sec": num_metrics / total_time,
            "breakdown": {
                "phase_transitions_us": (transition_time / (num_metrics // 4)) * 1_000_000,
                "gating_matrix_us": (gating_time / (num_metrics // 4)) * 1_000_000,
                "contradiction_us": (contradiction_time / (num_metrics // 4)) * 1_000_000,
                "threshold_adj_us": (threshold_time / (num_metrics // 4)) * 1_000_000
            }
        }
    
    def benchmark_complete_alert_evaluation(self, alert_engine, num_evaluations: int = 1000):
        """Benchmark complete alert evaluation cycle including all Phase 2A components"""
        
        # Setup realistic phase history
        now = datetime.utcnow()
        phases = [Phase.BTC, Phase.ETH, Phase.LARGE, Phase.ALT]
        
        for i in range(50):  # Populate history
            phase_state = Mock()
            phase_state.phase_now = phases[i % 4]
            phase_state.confidence = 0.7 + (i % 30) / 100
            phase_state.persistence_count = (i % 4) + 1
            alert_engine.phase_context.update_phase(
                phase_state, 
                contradiction_index=0.1 + (i % 40) / 100
            )
        
        # Prepare test signals
        base_signals = {
            "volatility": {"BTC": 0.25, "ETH": 0.20, "SOL": 0.30, "AVAX": 0.22},
            "correlation": {"avg_correlation": 0.65},
            "confidence": 0.8,
            "contradiction_index": 0.3
        }
        
        eval_times = []
        alert_types = [AlertType.VOL_Q90_CROSS, AlertType.CONTRADICTION_SPIKE, 
                      AlertType.CORR_HIGH, AlertType.DECISION_DROP]
        
        for i in range(num_evaluations):
            # Vary signals
            signals = {
                **base_signals,
                "confidence": 0.6 + (i % 40) / 100,
                "contradiction_index": 0.2 + (i % 50) / 100,
                "volatility": {
                    "BTC": 0.15 + (i % 30) / 100,
                    "ETH": 0.12 + (i % 25) / 100
                }
            }
            
            alert_type = alert_types[i % len(alert_types)]
            
            start = time.perf_counter()
            
            # This includes:
            # 1. Phase gating check
            # 2. Adaptive threshold calculation  
            # 3. Signal evaluation
            # 4. Metrics recording
            allowed, reason = alert_engine._check_phase_gating(alert_type, signals)
            
            if allowed:
                # Simulate rule evaluation (simplified)
                rule_config = alert_engine.config["alerting_config"]
                phase_context = {
                    "phase": alert_engine.phase_context.current_lagged_phase.phase if alert_engine.phase_context.current_lagged_phase else Phase.BTC,
                    "phase_factors": rule_config["phase_aware"]["phase_factors"],
                    "contradiction_index": signals["contradiction_index"]
                }
                
                # Adaptive threshold calculation is called during evaluation
                from services.alerts.alert_types import AlertRule
                test_rule = AlertRule(
                    alert_type=alert_type,
                    base_threshold=0.75,
                    adaptive_multiplier=1.0,
                    hysteresis_minutes=5,
                    severity_thresholds={"S1": 0.80, "S2": 0.85, "S3": 0.90},
                    suggested_actions={"S1": {"type": "acknowledge"}}
                )
                
                alert_engine.evaluator._calculate_adaptive_threshold(test_rule, signals, phase_context)
            
            eval_time = time.perf_counter() - start
            eval_times.append(eval_time)
        
        return {
            "num_evaluations": num_evaluations,
            "total_time_ms": sum(eval_times) * 1000,
            "avg_eval_time_us": mean(eval_times) * 1_000_000,
            "median_eval_time_us": sorted(eval_times)[num_evaluations // 2] * 1_000_000,
            "p95_eval_time_us": sorted(eval_times)[int(num_evaluations * 0.95)] * 1_000_000,
            "p99_eval_time_us": sorted(eval_times)[int(num_evaluations * 0.99)] * 1_000_000,
            "eval_rate_per_sec": num_evaluations / sum(eval_times),
            "std_dev_us": stdev(eval_times) * 1_000_000 if len(eval_times) > 1 else 0
        }
    
    def test_phase_history_performance_benchmark(self, alert_engine):
        """Test phase history management performance"""
        print("\n=== Phase History Management Benchmark ===")
        
        # Test different dataset sizes
        sizes = [100, 500, 1000, 2000]
        results = []
        
        for size in sizes:
            result = self.benchmark_phase_history_management(alert_engine, size)
            results.append(result)
            
            print(f"Size: {size:4d} snapshots")
            print(f"  Update time: {result['update_time_ms']:6.2f}ms")
            print(f"  Update rate: {result['update_rate_per_sec']:8.0f}/sec")
            print(f"  Avg per update: {result['avg_update_time_us']:6.1f}us")
            print(f"  Memory: {result['memory_mb']:6.1f}MB")
            print(f"  History cleanup: {result['original_history_size']} -> {result['cleaned_history_size']} ({result['cleanup_time_ms']:.2f}ms)")
            print()
        
        # Performance assertions (adjusted based on actual measurements)
        latest = results[-1]
        assert latest['avg_update_time_us'] < 200, f"Phase update too slow: {latest['avg_update_time_us']:.1f}us"
        assert latest['update_rate_per_sec'] > 5000, f"Update rate too low: {latest['update_rate_per_sec']:.0f}/sec"
        assert latest['cleanup_time_ms'] < 1, f"Cleanup too slow: {latest['cleanup_time_ms']:.2f}ms"
    
    def test_gating_matrix_performance_benchmark(self, alert_engine):
        """Test gating matrix lookup performance"""
        print("\n=== Gating Matrix Lookup Benchmark ===")
        
        result = self.benchmark_gating_matrix_lookups(alert_engine, 10000)
        
        print(f"Lookups: {result['num_lookups']:,}")
        print(f"Total time: {result['total_time_ms']:.2f}ms") 
        print(f"Average: {result['avg_lookup_time_us']:.1f}us")
        print(f"Median: {result['median_lookup_time_us']:.1f}us")
        print(f"P95: {result['p95_lookup_time_us']:.1f}us")
        print(f"P99: {result['p99_lookup_time_us']:.1f}us")
        print(f"Rate: {result['lookup_rate_per_sec']:,.0f}/sec")
        print(f"Std dev: {result['std_dev_us']:.1f}us")
        
        # Performance assertions  
        assert result['avg_lookup_time_us'] < 50, f"Gating lookup too slow: {result['avg_lookup_time_us']:.1f}us"
        assert result['p95_lookup_time_us'] < 100, f"P95 lookup too slow: {result['p95_lookup_time_us']:.1f}us"
        assert result['lookup_rate_per_sec'] > 50000, f"Lookup rate too low: {result['lookup_rate_per_sec']:,.0f}/sec"
    
    def test_adaptive_threshold_performance_benchmark(self, alert_engine):
        """Test adaptive threshold calculation performance"""
        print("\n=== Adaptive Threshold Calculation Benchmark ===")
        
        result = self.benchmark_adaptive_threshold_calculation(alert_engine, 5000)
        
        print(f"Calculations: {result['num_calculations']:,}")
        print(f"Total time: {result['total_time_ms']:.2f}ms")
        print(f"Average: {result['avg_calc_time_us']:.1f}us")
        print(f"Median: {result['median_calc_time_us']:.1f}us")
        print(f"P95: {result['p95_calc_time_us']:.1f}us")
        print(f"P99: {result['p99_calc_time_us']:.1f}us")
        print(f"Rate: {result['calc_rate_per_sec']:,.0f}/sec")
        print(f"Std dev: {result['std_dev_us']:.1f}us")
        
        # Performance assertions
        assert result['avg_calc_time_us'] < 200, f"Threshold calc too slow: {result['avg_calc_time_us']:.1f}us"
        assert result['p95_calc_time_us'] < 500, f"P95 calc too slow: {result['p95_calc_time_us']:.1f}us"
        assert result['calc_rate_per_sec'] > 5000, f"Calc rate too low: {result['calc_rate_per_sec']:,.0f}/sec"
    
    def test_metrics_recording_performance_benchmark(self, alert_engine):
        """Test Prometheus metrics recording performance"""
        print("\n=== Prometheus Metrics Recording Benchmark ===")
        
        result = self.benchmark_metrics_recording(alert_engine, 10000)
        
        print(f"Metrics recorded: {result['num_metrics']:,}")
        print(f"Total time: {result['total_time_ms']:.2f}ms")
        print(f"Average per metric: {result['avg_metric_time_us']:.1f}us")
        print(f"Rate: {result['metrics_rate_per_sec']:,.0f}/sec")
        print("Breakdown by metric type:")
        for metric_type, time_us in result['breakdown'].items():
            print(f"  {metric_type}: {time_us:.1f}us")
        
        # Performance assertions
        assert result['avg_metric_time_us'] < 50, f"Metrics recording too slow: {result['avg_metric_time_us']:.1f}us"
        assert result['metrics_rate_per_sec'] > 50000, f"Metrics rate too low: {result['metrics_rate_per_sec']:,.0f}/sec"
    
    def test_complete_evaluation_performance_benchmark(self, alert_engine):
        """Test complete alert evaluation performance including all Phase 2A components"""
        print("\n=== Complete Alert Evaluation Benchmark ===")
        
        result = self.benchmark_complete_alert_evaluation(alert_engine, 1000)
        
        print(f"Evaluations: {result['num_evaluations']:,}")
        print(f"Total time: {result['total_time_ms']:.2f}ms")
        print(f"Average: {result['avg_eval_time_us']:.1f}us")
        print(f"Median: {result['median_eval_time_us']:.1f}us")
        print(f"P95: {result['p95_eval_time_us']:.1f}us")
        print(f"P99: {result['p99_eval_time_us']:.1f}us")
        print(f"Rate: {result['eval_rate_per_sec']:,.0f}/sec")
        print(f"Std dev: {result['std_dev_us']:.1f}us")
        
        # Performance assertions (more relaxed for complete evaluation)
        assert result['avg_eval_time_us'] < 1000, f"Complete evaluation too slow: {result['avg_eval_time_us']:.1f}us"
        assert result['p95_eval_time_us'] < 2000, f"P95 evaluation too slow: {result['p95_eval_time_us']:.1f}us"
        assert result['eval_rate_per_sec'] > 1000, f"Evaluation rate too low: {result['eval_rate_per_sec']:,.0f}/sec"
        
        print(f"\nPhase 2A Performance Summary:")
        print(f"- Alert evaluation throughput: {result['eval_rate_per_sec']:,.0f}/sec")
        print(f"- Average latency: {result['avg_eval_time_us']:.0f}us")
        print(f"- P95 latency: {result['p95_eval_time_us']:.0f}us")


if __name__ == "__main__":
    # Run with: python -m pytest tests/performance/test_phase_aware_benchmarks.py -v -s
    pytest.main([__file__, "-v", "-s"])