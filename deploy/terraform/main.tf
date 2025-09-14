terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC and Networking
resource "aws_vpc" "crypto_rebal_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "crypto-rebal-vpc"
  }
}

resource "aws_internet_gateway" "crypto_rebal_igw" {
  vpc_id = aws_vpc.crypto_rebal_vpc.id

  tags = {
    Name = "crypto-rebal-igw"
  }
}

resource "aws_subnet" "public_subnet_1" {
  vpc_id                  = aws_vpc.crypto_rebal_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "crypto-rebal-public-1"
  }
}

resource "aws_subnet" "public_subnet_2" {
  vpc_id                  = aws_vpc.crypto_rebal_vpc.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "crypto-rebal-public-2"
  }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.crypto_rebal_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.crypto_rebal_igw.id
  }

  tags = {
    Name = "crypto-rebal-public-rt"
  }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_subnet_1.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_subnet_2.id
  route_table_id = aws_route_table.public_rt.id
}

# Security Groups
resource "aws_security_group" "alb_sg" {
  name        = "crypto-rebal-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.crypto_rebal_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "crypto-rebal-alb-sg"
  }
}

resource "aws_security_group" "ecs_sg" {
  name        = "crypto-rebal-ecs-sg"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.crypto_rebal_vpc.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "crypto-rebal-ecs-sg"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "crypto_rebal_cluster" {
  name = "crypto-rebal-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "crypto-rebal-cluster"
  }
}

# ECR Repository
resource "aws_ecr_repository" "crypto_rebal_repo" {
  name                 = "crypto-rebal"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "crypto-rebal-repo"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "crypto_rebal_task" {
  family                   = "crypto-rebal-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "crypto-rebal-api"
      image     = "${aws_ecr_repository.crypto_rebal_repo.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "LOG_LEVEL"
          value = "info"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.crypto_rebal_logs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "crypto-rebal-task"
  }
}

# Application Load Balancer
resource "aws_lb" "crypto_rebal_alb" {
  name               = "crypto-rebal-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [aws_subnet.public_subnet_1.id, aws_subnet.public_subnet_2.id]

  enable_deletion_protection = false

  tags = {
    Name = "crypto-rebal-alb"
  }
}

resource "aws_lb_target_group" "crypto_rebal_tg" {
  name        = "crypto-rebal-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.crypto_rebal_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name = "crypto-rebal-tg"
  }
}

resource "aws_lb_listener" "crypto_rebal_listener" {
  load_balancer_arn = aws_lb.crypto_rebal_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.crypto_rebal_tg.arn
  }
}

# ECS Service
resource "aws_ecs_service" "crypto_rebal_service" {
  name            = "crypto-rebal-service"
  cluster         = aws_ecs_cluster.crypto_rebal_cluster.id
  task_definition = aws_ecs_task_definition.crypto_rebal_task.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_sg.id]
    subnets          = [aws_subnet.public_subnet_1.id, aws_subnet.public_subnet_2.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.crypto_rebal_tg.arn
    container_name   = "crypto-rebal-api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.crypto_rebal_listener]

  tags = {
    Name = "crypto-rebal-service"
  }
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "crypto_rebal_logs" {
  name              = "/ecs/crypto-rebal"
  retention_in_days = 14

  tags = {
    Name = "crypto-rebal-logs"
  }
}

# IAM Roles
resource "aws_iam_role" "ecs_execution_role" {
  name = "crypto-rebal-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "crypto-rebal-ecs-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "crypto-rebal-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "crypto-rebal-ecs-task-role"
  }
}