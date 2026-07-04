# =============================================================================
# OmniMedical Suite v2.0 — AWS Infrastructure (EKS + RDS + ElastiCache + S3)
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }

  backend "s3" {
    bucket         = "omnimedical-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "omnimedical-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "omnimedical"
      Environment = var.environment
      ManagedBy   = "terraform"
      Version     = "2.0.0"
    }
  }
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# =============================================================================
# VPC & Networking
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-${var.environment}"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment == "staging"
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tags for Kubernetes integration
  public_subnet_tags = {
    "kubernetes.io/role/elb"                      = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"             = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }
}

# =============================================================================
# EKS Cluster
# =============================================================================

locals {
  cluster_name = "${var.project_name}-${var.environment}"
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = local.cluster_name
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Control plane logging
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  # Managed node groups
  eks_managed_node_groups = {
    general = {
      desired_size = var.node_desired_size
      min_size     = var.node_min_size
      max_size     = var.node_max_size

      instance_types = var.node_instance_types
      capacity_type  = var.environment == "production" ? "ON_DEMAND" : "SPOT"

      labels = {
        workload = "general"
      }

      taints = []

      # Disk encryption
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            encrypted             = true
            kms_key_id            = aws_kms_key.eks.arn
            delete_on_termination = true
          }
        }
      }
    }

    gpu = {
      desired_size = var.gpu_node_desired_size
      min_size     = var.gpu_node_min_size
      max_size     = var.gpu_node_max_size

      instance_types = ["g4dn.xlarge"]
      capacity_type  = "ON_DEMAND"

      labels = {
        workload = "gpu"
        nvidia.com/gpu = "true"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      ami_type = "AL2_x86_64_GPU"
    }
  }

  # Fargate profiles for serverless workloads
  fargate_profiles = {
    monitoring = {
      name = "monitoring"
      selectors = [
        { namespace = "kube-system" },
        { namespace = "monitoring" }
      ]
      subnets = module.vpc.private_subnets
    }
  }

  # Cluster addons
  cluster_addons = {
    coredns = {
      most_recent = true
      configuration_values = jsonencode({
        computeType = "Fargate"
      })
    }
    kube-proxy = { most_recent = true }
    vpc-cni = { most_recent = true }
    aws-ebs-csi-driver = { most_recent = true }
    aws-efs-csi-driver = { most_recent = true }
  }

  # IRSA (IAM Roles for Service Accounts)
  enable_irsa = true
}

# =============================================================================
# KMS Key for Encryption
# =============================================================================

resource "aws_kms_key" "eks" {
  description             = "EKS Secret Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${local.cluster_name}-eks"
  }
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${local.cluster_name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

# =============================================================================
# RDS PostgreSQL (Primary Database)
# =============================================================================

resource "aws_db_subnet_group" "main" {
  name       = "${local.cluster_name}-db"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "${local.cluster_name}-db"
  }
}

resource "aws_db_parameter_group" "main" {
  family = "postgres16"
  name   = "${local.cluster_name}-postgres16"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
}

resource "aws_db_instance" "main" {
  identifier = "${local.cluster_name}-postgres"

  engine         = "postgres"
  engine_version = "16.1"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.eks.arn

  db_name  = "omnimedical"
  username = "postgres"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  backup_retention_period = var.environment == "production" ? 30 : 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"

  multi_az               = var.environment == "production"
  deletion_protection    = var.environment == "production"
  skip_final_snapshot    = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.cluster_name}-final" : null

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  performance_insights_enabled    = var.environment == "production"
  performance_insights_retention_period = 7

  tags = {
    Name = "${local.cluster_name}-postgres"
  }
}

# =============================================================================
# ElastiCache Redis (Cache & Message Broker)
# =============================================================================

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.cluster_name}-cache"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_parameter_group" "main" {
  family = "redis7"
  name   = "${local.cluster_name}-redis7"
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.cluster_name}-redis"
  description          = "Redis cluster for OmniMedical"

  node_type            = var.cache_node_type
  num_cache_clusters   = var.environment == "production" ? 2 : 1

  engine_version       = "7.1"
  port                 = 6379

  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.cache.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = var.cache_auth_token

  automatic_failover_enabled = var.environment == "production"

  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window         = "05:00-06:00"

  tags = {
    Name = "${local.cluster_name}-redis"
  }
}

# =============================================================================
# S3 Buckets (Document Storage & Backups)
# =============================================================================

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-documents-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${local.cluster_name}-documents"
  }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.eks.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "archive-old-documents"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555  # 7 years (HIPAA retention)
    }
  }
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-backups-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${local.cluster_name}-backups"
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

# =============================================================================
# Security Groups
# =============================================================================

resource "aws_security_group" "db" {
  name_prefix = "${local.cluster_name}-db-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "PostgreSQL from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.cluster_name}-db"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "cache" {
  name_prefix = "${local.cluster_name}-cache-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Redis from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.cluster_name}-cache"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# IAM Roles & Policies
# =============================================================================

resource "aws_iam_policy" "s3_access" {
  name = "${local.cluster_name}-s3-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*",
          aws_s3_bucket.backups.arn,
          "${aws_s3_bucket.backups.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "kms_access" {
  name = "${local.cluster_name}-kms-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.eks.arn
      }
    ]
  })
}
