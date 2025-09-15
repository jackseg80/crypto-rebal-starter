# Phase 2A Grafana Dashboards

This directory contains comprehensive Grafana dashboards for monitoring the Phase 2A Alert System.

## Dashboards

### 1. Alert System Monitoring (`alert_system_dashboard.json`)
- **Alert Generation Rate**: Real-time alert generation metrics
- **Active Alerts by Severity**: S1/S2/S3 alert distribution
- **Storage Mode & Degradation**: Current storage state monitoring
- **Engine Performance**: Alert evaluation duration and timing
- **Storage Operations**: Performance metrics for Redis/File/Memory
- **Rate Limiting**: Rate limit hits and budget tracking
- **ML Signal Quality**: Machine learning signal health metrics
- **Alert Actions**: Acknowledgments, snoozing, and escalations
- **Lua Script Performance**: Redis Lua script execution metrics

### 2. Storage Performance & Degradation (`storage_performance_dashboard.json`)
- **Storage Mode Status**: Current storage mode (Redis/File/Memory)
- **Degradation Alerts**: Real-time degradation monitoring
- **Performance Benchmarks**: P95/P99 latency tracking
- **Success Rates**: Operation success rates by storage type
- **Failure Analysis**: Redis and file system failure rates
- **Lua Script Monitoring**: Comprehensive Lua performance metrics

## Quick Setup (Docker Compose)

```yaml
# docker-compose.grafana.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus:/etc/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning
      - ./config/grafana:/etc/grafana/provisioning/dashboards/crypto-rebal
```

## Manual Setup

### 1. Add Prometheus Datasource
- URL: `http://localhost:9090` (or your Prometheus server)
- Access: Server (default)
- Scrape interval: 30s

### 2. Import Dashboards
1. Go to Grafana → Dashboards → Import
2. Upload `alert_system_dashboard.json`
3. Upload `storage_performance_dashboard.json`
4. Set datasource to your Prometheus instance

### 3. Configure Prometheus Scraping

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'crypto-rebal-alerts'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/alerts/metrics/prometheus'
    scrape_interval: 30s
    scrape_timeout: 10s
```

## Key Metrics Overview

### Performance Targets (from Phase 2A)
- **Store P95 Latency**: < 100ms (achieved: 0.15ms)
- **Get P95 Latency**: < 50ms (achieved: 0.03ms)
- **Throughput**: > 100 ops/s (achieved: 80,445 ops/s)

### Critical Alerts in Grafana
- **Storage Degradation**: When storage_mode != "redis" 
- **High Latency**: P95 latency > 100ms
- **Low Success Rate**: Lua script success < 99%
- **Redis Failures**: Redis failure rate > 0

### Dashboard Refresh Rates
- **Alert System Dashboard**: 30s refresh (overview)
- **Storage Performance Dashboard**: 10s refresh (detailed monitoring)

## Production Considerations

### Retention Policy
```yaml
# In prometheus.yml
global:
  scrape_interval: 30s
  evaluation_interval: 30s
  
rule_files:
  - "alert_rules.yml"

# Storage retention
storage:
  retention.time: 15d
  retention.size: 10GB
```

### Alerting Rules Example
```yaml
# alert_rules.yml
groups:
  - name: crypto-rebal-alerts
    rules:
      - alert: StorageDegraded
        expr: crypto_rebal_alert_storage_degraded == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Alert storage is degraded"
          description: "Storage has fallen back to {{$labels.storage_mode}} mode"
      
      - alert: HighAlertLatency
        expr: histogram_quantile(0.95, crypto_rebal_alert_storage_operation_duration_seconds_bucket) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Alert storage P95 latency too high"
          description: "P95 latency is {{$value}}s, above 100ms threshold"
```

## Troubleshooting

### Common Issues

1. **No Data in Dashboards**
   - Check Prometheus scraping: `http://localhost:9090/targets`
   - Verify API endpoint: `http://localhost:8000/api/alerts/metrics/prometheus`
   - Check Grafana datasource connection

2. **Missing Metrics**
   - Ensure AlertEngine is running and processing alerts
   - Check for Redis connectivity issues
   - Verify Prometheus metrics are being updated

3. **Performance Issues**
   - Reduce scrape frequency for high-load environments
   - Use recording rules for complex queries
   - Consider metric relabeling to reduce cardinality

### Health Check Commands

```bash
# Test Prometheus metrics endpoint
curl http://localhost:8000/api/alerts/metrics/prometheus

# Check Grafana API
curl -u admin:admin123 http://localhost:3000/api/health

# Verify dashboard import
curl -u admin:admin123 http://localhost:3000/api/dashboards/home
```

---

*Phase 2A Alert System Monitoring | Generated: 2025-09-10*