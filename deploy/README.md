# Deployment Guide

This guide covers deploying the crypto-rebal application to various cloud platforms.

## Available Deployment Options

### 1. Docker Compose (Local/VPS)

**Quick Start:**
```bash
cd docker
docker-compose up -d
```

**Features:**
- Redis caching
- Health checks
- Auto-restart policies
- Volume persistence

**Access:** http://localhost:8080

### 2. AWS ECS with Terraform

**Prerequisites:**
```bash
# Install required tools
brew install terraform awscli    # macOS
# or
sudo apt-get install terraform awscli  # Ubuntu

# Configure AWS credentials
aws configure
```

**Deploy:**
```bash
# Set environment variables
export AWS_ACCOUNT_ID="123456789012"
export AWS_REGION="us-east-1"
export ENVIRONMENT="prod"

# Build and push Docker image
./scripts/build-docker.sh

# Deploy infrastructure
./scripts/deploy-aws.sh
```

**Features:**
- Auto-scaling ECS service
- Application Load Balancer
- CloudWatch logging
- ECR container registry
- Health checks with auto-recovery

**Cost:** ~$20-50/month (depending on usage)

### 3. Kubernetes

**Deploy:**
```bash
# Apply Kubernetes manifests
kubectl apply -f deploy/kubernetes.yml

# Check deployment status
kubectl get pods -n crypto-rebal
kubectl get services -n crypto-rebal
```

**Features:**
- 2 replica pods for high availability
- Persistent storage for data/cache
- Redis sidecar
- Resource limits and requests

## Environment Configuration

### Required Environment Variables

```bash
# Production settings
ENVIRONMENT=production
LOG_LEVEL=info

# Cache settings
CACHE_ENABLED=true
MAX_CACHE_SIZE=1000

# Redis (if using external Redis)
REDIS_HOST=redis-service
REDIS_PORT=6379

# Security
DEBUG=false
APP_DEBUG=false
```

### Optional Environment Variables

```bash
# CORS settings
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Database (for future use)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# API Keys (encrypted)
COINTRACKING_API_KEY=your_encrypted_key
KRAKEN_API_KEY=your_encrypted_key
```

## Health Checks

All deployment methods include health checks:

- **Endpoint:** `/health`
- **Timeout:** 10 seconds
- **Interval:** 30 seconds
- **Retries:** 3 attempts

## Monitoring

### AWS CloudWatch (ECS deployment)
- Application logs: `/ecs/crypto-rebal`
- Metrics: CPU, Memory, Request count
- Alarms: High error rate, resource usage

### Kubernetes Monitoring
```bash
# View logs
kubectl logs -f deployment/crypto-rebal-api -n crypto-rebal

# View metrics
kubectl top pods -n crypto-rebal
```

### Application Monitoring
- Health endpoint: `/health/detailed`
- Performance metrics: `/api/performance/system/memory`
- Cache statistics: `/api/performance/cache/stats`

## Scaling

### Horizontal Scaling

**AWS ECS:**
```bash
# Update desired count in Terraform
terraform apply -var="instance_count=4"
```

**Kubernetes:**
```bash
# Scale replicas
kubectl scale deployment crypto-rebal-api --replicas=4 -n crypto-rebal
```

### Vertical Scaling

**AWS ECS:**
```bash
# Update resources in Terraform
terraform apply -var="cpu=512" -var="memory=1024"
```

**Kubernetes:**
Edit `deploy/kubernetes.yml` resource limits and apply.

## Security

### Network Security
- All deployments use security groups/network policies
- Only necessary ports exposed (80, 443, 8000)
- HTTPS termination at load balancer

### Application Security
- No secrets in environment variables (use AWS Secrets Manager/Kubernetes Secrets)
- Regular security updates via base image updates
- Container runs as non-root user

### Data Security
- All sensitive data encrypted at rest
- Redis password protection enabled
- API key encryption for external services

## Backup & Recovery

### Data Backup
```bash
# Backup price history data
kubectl exec -it deployment/crypto-rebal-api -- tar -czf /tmp/backup.tar.gz /app/data

# Backup cache
kubectl exec -it deployment/redis -- redis-cli SAVE
```

### Disaster Recovery
1. Infrastructure: Terraform state stored in S3 (recommended)
2. Data: Regular automated backups to S3
3. Recovery time: < 15 minutes with proper automation

## Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker logs crypto-rebal-api
kubectl logs deployment/crypto-rebal-api

# Check health endpoint
curl http://localhost:8080/health
```

**High memory usage:**
- Check cache settings: `/api/performance/cache/stats`
- Clear cache: `POST /api/performance/cache/clear`
- Monitor: `/api/performance/system/memory`

**Slow optimization:**
- Enable performance mode for large portfolios
- Check asset count (>200 assets use optimized algorithm)
- Monitor: `/api/performance/optimization/benchmark`

### Support
- Check application logs first
- Use health/detailed endpoint for diagnostics
- Performance monitoring endpoints for optimization issues
- GitHub Issues for bugs/feature requests

## Cost Optimization

### AWS ECS
- Use Spot instances for non-critical workloads
- Right-size CPU/memory based on monitoring
- Use scheduled scaling for predictable patterns

### General
- Enable caching to reduce external API calls
- Optimize container image size (multi-stage builds)
- Monitor and optimize database queries
