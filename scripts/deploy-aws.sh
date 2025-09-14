#!/bin/bash

# AWS deployment script using Terraform

set -e

TERRAFORM_DIR="deploy/terraform"
ENVIRONMENT=${ENVIRONMENT:-prod}
AWS_REGION=${AWS_REGION:-us-east-1}

echo "[DEPLOY] Starting AWS deployment for environment: $ENVIRONMENT"

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "[ERROR] Terraform is not installed. Please install Terraform first."
    exit 1
fi

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    echo "[ERROR] AWS CLI is not installed. Please install AWS CLI first."
    exit 1
fi

# Verify AWS credentials
echo "[AUTH] Verifying AWS credentials..."
aws sts get-caller-identity > /dev/null || {
    echo "[ERROR] AWS credentials not configured. Run 'aws configure' first."
    exit 1
}

cd $TERRAFORM_DIR

# Initialize Terraform
echo "[TERRAFORM] Initializing Terraform..."
terraform init

# Plan deployment
echo "[TERRAFORM] Creating deployment plan..."
terraform plan \
    -var="environment=$ENVIRONMENT" \
    -var="aws_region=$AWS_REGION" \
    -out=tfplan

# Ask for confirmation
read -p "Do you want to apply this plan? (y/N): " confirm
if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "[ABORT] Deployment cancelled by user"
    exit 0
fi

# Apply deployment
echo "[TERRAFORM] Applying deployment..."
terraform apply tfplan

# Get outputs
echo "[INFO] Deployment completed! Here are the important endpoints:"
echo "Load Balancer DNS: $(terraform output -raw load_balancer_dns)"
echo "ECR Repository: $(terraform output -raw ecr_repository_url)"
echo "ECS Cluster: $(terraform output -raw ecs_cluster_name)"

echo "[SUCCESS] AWS deployment completed successfully!"
echo "[NEXT] Don't forget to:"
echo "  1. Build and push your Docker image to ECR"
echo "  2. Update your ECS service to use the new image"
echo "  3. Configure your domain DNS to point to the load balancer"