###############################################################################
# OmniMedical Suite - AWS EKS Infrastructure
# Terraform >= 1.5 | AWS Provider >= 5.0
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # Uncomment and configure backend for production state management
  # backend "s3" {
  #   bucket         = "omnimedical-terraform-state"
  #   key            = "eks/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-lock"
  # }
}

###############################################################################
# Provider
###############################################################################

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "OmniMedicalSuite"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

###############################################################################
# Data Sources
###############################################################################

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  # Environment-specific naming
  name_prefix = "${var.cluster_name}-${var.environment}"

  # EKS addon versions pinned for stability
  cluster_version = "1.29"

  # Common security group IDs (resolved after creation)
  vpc_id = module.vpc.vpc_id
}

###############################################################################
# KMS Encryption Key
###############################################################################

module "kms" {
  source  = "terraform-aws-modules/kms/aws"
  version = "~> 3.0"

  description             = "OmniMedical Suite EKS & RDS encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  aliases = [
    "alias/${local.name_prefix}-encryption"
  ]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccountAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowEKSAccess"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowRDSAccess"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

###############################################################################
# VPC — 3 AZs, public + private subnets, NAT + IGW
###############################################################################

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  public_subnets  = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i + 3)]

  enable_nat_gateway   = true
  single_nat_gateway   = false        # one NAT per AZ for HA
  enable_vpn_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tag subnets for EKS load-balancer & cluster auto-discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

###############################################################################
# Security Groups
###############################################################################

# --- EKS Cluster Security Group ---
resource "aws_security_group" "eks_cluster" {
  name        = "${local.name_prefix}-eks-cluster-sg"
  description = "Security group for EKS cluster control plane"
  vpc_id      = local.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-eks-cluster-sg"
  }
}

# --- EKS Node Security Group ---
resource "aws_security_group" "eks_nodes" {
  name        = "${local.name_prefix}-eks-nodes-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = local.vpc_id

  ingress {
    description = "Cluster API to nodes"
    from_port   = 1025
    to_port     = 65535
    protocol    = "tcp"
    security_groups = [aws_security_group.eks_cluster.id]
  }

  ingress {
    description = "Node-to-node communication"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name                                        = "${local.name_prefix}-eks-nodes-sg"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  }
}

# --- RDS Security Group ---
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "PostgreSQL access restricted to EKS private subnets"
  vpc_id      = local.vpc_id

  ingress {
    description     = "PostgreSQL from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-rds-sg" }
}

# --- ElastiCache Redis Security Group ---
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Redis access restricted to EKS private subnets"
  vpc_id      = local.vpc_id

  ingress {
    description     = "Redis from EKS nodes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-redis-sg" }
}

# --- ALB / Ingress Security Group ---
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Application Load Balancer — HTTPS ingress from internet"
  vpc_id      = local.vpc_id

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-alb-sg" }
}

# --- EFS Security Group ---
resource "aws_security_group" "efs" {
  name        = "${local.name_prefix}-efs-sg"
  description = "EFS access restricted to EKS nodes"
  vpc_id      = local.vpc_id

  ingress {
    description     = "NFS from EKS nodes"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-efs-sg" }
}

###############################################################################
# EKS Cluster
###############################################################################

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = local.cluster_version

  # ------------------------------------------------------------------
  # VPC & networking
  # ------------------------------------------------------------------
  vpc_id     = local.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # ------------------------------------------------------------------
  # Encryption — secrets & config-map use KMS
  # ------------------------------------------------------------------
  cluster_encryption_config = {
    provider_key_arn = module.kms.key_arn
    resources        = ["secrets"]
  }

  # ------------------------------------------------------------------
  # IAM Roles with IRSA
  # ------------------------------------------------------------------
  cluster_identity_providers = {}

  iam_role_additional_policies = {
    additional = [
      "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
      "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    ]
  }

  # ------------------------------------------------------------------
  # EKS Add-ons
  # ------------------------------------------------------------------
  cluster_addons = {
    vpc-cni = {
      most_recent    = true
      before_compute = true
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # ------------------------------------------------------------------
  # Managed Node Groups
  # ------------------------------------------------------------------

  # Primary compute node group — ON_DEMAND
  eks_managed_node_groups = {
    main = {
      name           = "${var.cluster_name}-main"
      instance_types = [var.instance_type]
      capacity_type  = "ON_DEMAND"
      min_size       = var.node_min_count
      max_size       = var.node_max_count
      desired_size   = var.node_desired_count

      subnet_ids = module.vpc.private_subnets

      ami_type       = "AL2_x86_64"
      platform       = "linux"
      release_version = "" # use default for cluster version

      labels = {
        role       = "main"
        workload   = "general"
        gpu-support = "false"
      }

      taints = []

      update_config = {
        max_unavailable_percentage = 33
      }

      iam_role_additional_policies = {
        AmazonEC2ContainerRegistryReadOnly = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
        CloudWatchFullAccess               = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
        S3Access                          = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
      }
    }

    # GPU node group — SPOT (optional)
    gpu = {
      name           = "${var.cluster_name}-gpu"
      instance_types = [var.gpu_instance_type]
      capacity_type  = "SPOT"
      min_size       = 0
      max_size       = var.gpu_max_count
      desired_size   = 0

      subnet_ids = module.vpc.private_subnets

      ami_type = "AL2_x86_64_GPU"

      labels = {
        role      = "gpu"
        workload  = "ml-training"
        nvidia-gpu = "true"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "present"
        effect = "NO_SCHEDULE"
      }]

      update_config = {
        max_unavailable_percentage = 50
      }

      iam_role_additional_policies = {
        AmazonEC2ContainerRegistryReadOnly = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
        CloudWatchFullAccess               = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
        S3FullAccess                       = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
      }
    }
  }

  # Prevent destroying cluster accidentally
  enable_cluster_creator_admin_permissions = true

  tags = {
    Name = var.cluster_name
  }
}

# IRSA role for AWS EBS CSI Driver
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${var.cluster_name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

###############################################################################
# Application Load Balancer
###############################################################################

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = false

  drop_invalid_header_fields = true

  access_logs {
    enabled = var.enable_monitoring
    bucket  = aws_s3_bucket.access_logs.id
    prefix  = "alb-access-logs"
  }

  tags = {
    Name = "${local.name_prefix}-alb"
  }
}

# ALB target group (HTTP → forwarded to EKS ingress)
resource "aws_lb_target_group" "http" {
  name     = "${local.name_prefix}-http-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = local.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 3
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    timeout             = 5
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name_prefix}-http-tg" }
}

# ALB HTTPS listener (placeholder — ACM cert must be attached manually or via Route53)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = try(data.aws_acm_certificate.default[0].arn, "")

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.http.arn
  }

  depends_on = [aws_lb_target_group.http]
}

# HTTP → HTTPS redirect listener
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Attempt to look up an existing ACM cert (non-breaking if absent)
data "aws_acm_certificate" "default" {
  count    = var.acm_certificate_arn != "" ? 1 : 0
  domain   = var.acm_certificate_domain
  statuses = ["ISSUED"]
  types    = ["AMAZON_ISSUED"]
}

###############################################################################
# RDS PostgreSQL
###############################################################################

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${local.name_prefix}-db"

  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = var.db_instance_class
  allocated_storage    = 100
  storage_encrypted    = true
  kms_key_id           = module.kms.key_arn
  storage_type         = "gp3"
  iops                 = 3000

  # Multi-AZ for production resilience
  multi_az               = var.db_multi_az
  db_name                = var.db_name
  username               = "omnimed_admin"
  manage_master_user_password = true

  # Automated backups
  backup_retention_period = var.enable_backup ? 30 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"
  deletion_protection     = true

  # Network
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = module.vpc.database_subnet_group_name

  # Performance insights (optional)
  performance_insights_enabled          = var.enable_monitoring
  performance_insights_retention_period = var.enable_monitoring ? 7 : 0

  # Parameters tuned for medical workload
  parameter_group_name = "default.postgres15"
  parameters = [
    { name = "log_connections", value = "1" },
    { name = "log_disconnections", value = "1" },
    { name = "pgaudit.log", value = "write,ddl" },
    { name = "shared_preload_libraries", value = "pgaudit" },
  ]

  tags = {
    Name = "${local.name_prefix}-postgresql"
  }
}

###############################################################################
# ElastiCache Redis
###############################################################################

module "redis" {
  source  = "terraform-aws-modules/elasticache/aws"
  version = "~> 1.0"

  cluster_id = "${local.name_prefix}-redis"

  engine            = "redis"
  engine_version    = "7.0"
  node_type         = var.redis_node_type
  num_cache_clusters = length(local.azs)       # one per AZ
  parameter_group_name = "default.redis7"

  # Network
  subnet_group_name    = module.vpc.elasticache_subnet_group_name
  security_group_ids   = [aws_security_group.redis.id]

  # At-rest encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth_token.result

  # Automatic backups
  automatic_failover_enabled = true
  multi_az_enabled           = true
  snapshot_retention_limit   = var.enable_backup ? 7 : 0
  snapshot_window            = "05:00-06:00"

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}

resource "random_password" "redis_auth_token" {
  length  = 32
  special = false
}

# Store Redis auth token in Secrets Manager
resource "aws_secretsmanager_secret" "redis_auth" {
  name                    = "${local.name_prefix}/redis/auth-token"
  recovery_window_in_days = 30

  tags = { Name = "${local.name_prefix}-redis-auth" }
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id = aws_secretsmanager_secret.redis_auth.id
  secret_string = jsonencode({
    auth_token = random_password.redis_auth_token.result
  })
}

###############################################################################
# S3 Buckets
###############################################################################

# --- Documents Bucket ---
resource "aws_s3_bucket" "documents" {
  bucket = "${local.name_prefix}-documents-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${local.name_prefix}-documents" }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms.key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Backups Bucket ---
resource "aws_s3_bucket" "backups" {
  bucket = "${local.name_prefix}-backups-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${local.name_prefix}-backups" }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms.key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-old-backups"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- ALB Access Logs Bucket ---
resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.name_prefix}-alb-logs-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${local.name_prefix}-alb-logs" }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    expiration { days = 90 }
  }
}

###############################################################################
# EFS — Shared model cache (NFS for pod-to-pod sharing)
###############################################################################

module "efs" {
  source  = "terraform-aws-modules/efs/aws"
  version = "~> 1.0"

  creation_token = "${local.name_prefix}-model-cache"
  name           = "${local.name_prefix}-model-cache"

  # Encrypt at rest
  encrypted = true
  kms_key_id = module.kms.key_arn

  # Performance mode: general purpose, burst throughput
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  # Mount targets — one per private subnet
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.efs.id]

  # Enable automatic backups
  enable_backup_policy = var.enable_backup

  tags = {
    Name = "${local.name_prefix}-model-cache-efs"
  }
}

###############################################################################
# IAM Roles for IRSA — application service accounts
###############################################################################

# --- API Service Account Role ---
module "api_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name_prefix = "${var.cluster_name}-api-"
  role_description = "IRSA role for OmniMedical API pods"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["omnimedical:api-service"]
    }
  }

  role_policy_arns = {
    s3_docs  = aws_iam_policy.api_s3.arn
    secrets  = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
  }
}

resource "aws_iam_policy" "api_s3" {
  name        = "${local.name_prefix}-api-s3-policy"
  description = "S3 access for OmniMedical API"

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

# --- GPU Training Job Role ---
module "training_irsa" {
  count = var.enable_gpu_node_group ? 1 : 0

  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name_prefix = "${var.cluster_name}-training-"
  role_description = "IRSA role for OmniMedical GPU training pods"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["omnimedical:training-job"]
    }
  }

  role_policy_arns = {
    s3_full = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
    ecr     = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
    efs     = aws_iam_policy.training_efs[0].arn
  }
}

resource "aws_iam_policy" "training_efs" {
  count = var.enable_gpu_node_group ? 1 : 0

  name        = "${local.name_prefix}-training-efs-policy"
  description = "EFS access for training pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["efs:*"]
        Resource = [module.efs.arn]
      }
    ]
  })
}

###############################################################################
# CloudWatch Log Group — unified cluster logs
###############################################################################

resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.enable_backup ? 90 : 30

  tags = { Name = "${local.name_prefix}-eks-logs" }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/omnimedical/app"
  retention_in_days = var.enable_backup ? 90 : 30

  tags = { Name = "${local.name_prefix}-app-logs" }
}

###############################################################################
# GuardDuty & Config (optional monitoring)
###############################################################################

resource "aws_cloudwatch_dashboard" "main" {
  count = var.enable_monitoring ? 1 : 0

  dashboard_name = "${local.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title = "EKS Cluster CPU / Memory"
          metrics = [
            ["AWS/EKS", "ClusterCPUUtilization", "ClusterName", var.cluster_name, { "stat" : "Average", "period" : 300 }],
            [".", "ClusterMemoryUtilization", ".", ".", { "stat" : "Average" }]
          ]
          region = var.region
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title = "RDS — CPU / Connections"
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", module.db.db_instance_id, { "stat" : "Average", "period" : 300 }],
            [".", "DatabaseConnections", ".", ".", { "stat" : "Average" }]
          ]
          region = var.region
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title = "ALB — Request Count / 5xx"
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.main.arn_suffix, { "stat" : "Sum", "period" : 300 }],
            [".", "HTTPCode_Target_5XX_Count", ".", ".", { "stat" : "Sum" }]
          ]
          region = var.region
        }
      }
    ]
  })
}
