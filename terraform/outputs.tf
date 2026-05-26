###############################################################################
# OmniMedical Suite — Terraform Outputs
###############################################################################

# ---------------------------------------------------------------------------
# EKS Cluster
# ---------------------------------------------------------------------------

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS cluster API server"
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_version" {
  description = "Kubernetes version of the EKS cluster"
  value       = module.eks.cluster_version
}

output "configure_kubectl" {
  description = "Command to configure kubectl to connect to the cluster"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the cluster"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider (for IRSA)"
  value       = module.eks.oidc_provider_arn
}

# ---------------------------------------------------------------------------
# RDS
# ---------------------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS PostgreSQL connection endpoint"
  value       = module.db.db_instance_endpoint
}

output "rds_instance_id" {
  description = "RDS instance identifier"
  value       = module.db.db_instance_id
}

output "rds_database_name" {
  description = "RDS database name"
  value       = module.db.db_name
}

# ---------------------------------------------------------------------------
# ElastiCache Redis
# ---------------------------------------------------------------------------

output "redis_endpoint" {
  description = "Primary Redis endpoint (without auth token — retrieve from Secrets Manager)"
  value       = module.redis.cluster_member[0].address
}

output "redis_port" {
  description = "Redis port"
  value       = module.redis.cluster_member[0].port
}

output "redis_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Redis auth token"
  value       = aws_secretsmanager_secret.redis_auth.arn
}

# ---------------------------------------------------------------------------
# ALB
# ---------------------------------------------------------------------------

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Hosted zone ID of the ALB (for Route53 alias records)"
  value       = aws_lb.main.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

# ---------------------------------------------------------------------------
# S3 Buckets
# ---------------------------------------------------------------------------

output "s3_documents_bucket" {
  description = "Name of the S3 documents bucket"
  value       = aws_s3_bucket.documents.id
}

output "s3_backups_bucket" {
  description = "Name of the S3 backups bucket"
  value       = aws_s3_bucket.backups.id
}

output "s3_bucket_names" {
  description = "Map of bucket purpose to bucket name"
  value = {
    documents  = aws_s3_bucket.documents.id
    backups    = aws_s3_bucket.backups.id
    access_logs = aws_s3_bucket.access_logs.id
  }
}

# ---------------------------------------------------------------------------
# KMS
# ---------------------------------------------------------------------------

output "kms_key_arn" {
  description = "ARN of the KMS encryption key"
  value       = module.kms.key_arn
}

output "kms_key_id" {
  description = "ID of the KMS encryption key"
  value       = module.kms.key_id
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------

output "vpc_id" {
  description = "VPC identifier"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnets
}

# ---------------------------------------------------------------------------
# EFS
# ---------------------------------------------------------------------------

output "efs_id" {
  description = "EFS file system ID"
  value       = module.efs.id
}

output "efs_dns_name" {
  description = "EFS DNS name for mounting in pods"
  value       = module.efs.dns_name
}

# ---------------------------------------------------------------------------
# IAM / IRSA
# ---------------------------------------------------------------------------

output "api_irsa_role_arn" {
  description = "IAM role ARN for the API service account (IRSA)"
  value       = module.api_irsa.iam_role_arn
}

output "training_irsa_role_arn" {
  description = "IAM role ARN for the training job service account (IRSA). Empty if GPU node group is disabled."
  value       = var.enable_gpu_node_group ? module.training_irsa[0].iam_role_arn : ""
}
