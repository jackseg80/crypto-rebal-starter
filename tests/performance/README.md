# Alert Storage Performance Benchmarks - Phase 2A

This directory contains performance benchmarks for the Phase 2A Alert Storage system.

## Phase 2A Architecture

The enhanced alert storage implements:
- **Redis ZSET/HASH**: Time-ordered alert indexing with structured data storage
- **Lua Atomic Scripts**: Atomic operations for deduplication, rate limiting, and retrieval
- **Cascade Fallback**: Redis → File → In-memory degradation with observability
- **Enhanced Metrics**: Degradation tracking and performance monitoring

## Performance Targets

Based on user requirements for production deployment:

| Metric | Target | Description |
|--------|--------|-------------|
| Store P95 | < 100ms | 95th percentile latency for alert storage (CPU bound) |
| Get P95 | < 50ms | 95th percentile latency for active alert retrieval |
| Throughput | > 100 ops/sec | Concurrent operations per second |
| Fallback | < 200ms P95 | Performance during degraded mode |

## Running Benchmarks

### Full Benchmark Suite

```bash
# With Redis (recommended)
python tests/performance/benchmark_alert_storage.py --redis-url "redis://localhost:6379"

# File/Memory only
python tests/performance/benchmark_alert_storage.py

# Quick test (fewer operations)
python tests/performance/benchmark_alert_storage.py --quick --redis-url "redis://localhost:6379"
```

### Sample Output

```
================================================================================
PHASE 2A ALERT STORAGE PERFORMANCE BENCHMARK
================================================================================
Redis URL: redis://localhost:6379
Start time: 2025-09-10 14:30:00

[BENCHMARK] Testing Redis_Cascade mode (1000 operations)
  Store P95: 45.32ms, P99: 78.45ms
  Get P95: 23.67ms, P99: 41.23ms

[BENCHMARK] Testing concurrent operations (10 threads, 50 ops each)
  Concurrent P95: 52.18ms, P99: 89.34ms
  Throughput: 156.7 ops/sec

[PERFORMANCE TARGETS]
  Store P95 Target:  < 100ms   ✓ PASS (45.32ms)
  Get P95 Target:    < 50ms    ✓ PASS (23.67ms)
  Throughput Target: > 100 ops/s  ✓ PASS (156.7 ops/s)

[OVERALL] Phase 2A Performance: ✓ MEETS TARGETS
```

## Benchmark Components

### 1. Single-Threaded Performance
- **Store Operations**: Measures alert storage latency with deduplication
- **Get Operations**: Measures active alert retrieval with filtering
- **Different Storage Modes**: Redis, File, Memory cascade testing

### 2. Concurrent Performance  
- **Multi-threaded**: 10 concurrent threads storing alerts
- **Throughput Measurement**: Operations per second under load
- **Contention Testing**: Lock and atomic operation performance

### 3. Fallback Cascade Testing
- **Mode Comparison**: Redis vs File vs Memory performance
- **Degradation Impact**: Latency increase during fallback
- **Recovery Testing**: Performance after mode restoration

### 4. Legacy Comparison
- **Backward Compatibility**: Phase 1 vs Phase 2A performance
- **Feature Overhead**: Cost of enhanced functionality
- **Migration Impact**: Performance difference analysis

## Result Files

Benchmark results are saved as JSON files with timestamps:
```
benchmark_results_phase2a_20250910_143000.json
```

Each result file contains:
- Detailed latency percentiles (P50, P95, P99)
- Throughput measurements
- Storage mode comparisons
- Memory usage patterns
- Error rates and degradation metrics

## Performance Analysis

### Expected Results

**Redis Mode (Optimal)**:
- Store P95: 30-60ms (Lua script overhead)
- Get P95: 15-35ms (ZSET range queries)
- Throughput: 200-400 ops/sec

**File Mode (Fallback)**:
- Store P95: 80-150ms (File I/O + locking)
- Get P95: 40-80ms (JSON parsing)
- Throughput: 50-100 ops/sec

**Memory Mode (Degraded)**:
- Store P95: 5-15ms (In-memory operations)
- Get P95: 10-25ms (List filtering)
- Throughput: 500+ ops/sec (but volatile)

### Performance Factors

1. **Redis Network Latency**: Local vs remote Redis instance
2. **Lua Script Complexity**: Atomic operation overhead
3. **File System Performance**: SSD vs HDD impact
4. **Memory Pressure**: GC impact during high load
5. **Concurrent Access**: Lock contention in file mode

## Troubleshooting

### Poor Redis Performance
- Check Redis memory configuration
- Verify network latency to Redis
- Monitor Redis CPU usage during benchmark
- Check Lua script compilation time

### High File Mode Latency
- Verify disk I/O performance
- Check file system type (NTFS vs ext4)
- Monitor disk queue depth
- Verify file locking implementation

### Memory Mode Issues
- Monitor Python memory usage
- Check GC frequency during benchmark
- Verify thread safety of in-memory operations

## Integration with CI/CD

The benchmark can be integrated into CI/CD pipelines:

```bash
# Exit code 0 if all targets met, 1 otherwise
python tests/performance/benchmark_alert_storage.py --redis-url "$REDIS_URL"
echo $? # 0 = success, 1 = performance regression
```

This ensures performance regressions are caught before production deployment.