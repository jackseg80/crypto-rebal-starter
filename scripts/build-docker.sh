#!/bin/bash

# Build and deploy script for crypto-rebal application

set -e

echo "[BUILD] Building crypto-rebal Docker image..."

# Build Docker image
docker build -f docker/Dockerfile -t crypto-rebal:latest .

echo "[BUILD] Docker image built successfully"

# Tag for ECR (if AWS_ACCOUNT_ID and AWS_REGION are set)
if [ ! -z "$AWS_ACCOUNT_ID" ] && [ ! -z "$AWS_REGION" ]; then
    ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/crypto-rebal:latest"
    echo "[TAG] Tagging image for ECR: $ECR_URI"
    docker tag crypto-rebal:latest $ECR_URI
    
    # Login to ECR
    echo "[AUTH] Logging into ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Push to ECR
    echo "[PUSH] Pushing to ECR..."
    docker push $ECR_URI
    
    echo "[DONE] Image pushed to ECR successfully"
else
    echo "[INFO] AWS_ACCOUNT_ID and AWS_REGION not set - skipping ECR push"
fi

echo "[SUCCESS] Build completed!"