###############################################################################
# OmniMedical Suite — Terraform Input Variables
###############################################################################

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

variable "cluster_name" {
  description = "Name of the EKS cluster and primary resource prefix"
  type        = string
  default     = "omnimedical-suite"
}

variable "environment" {
  description = "Deployment environment (development, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be one of: development, staging, production."
  }
}

variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones (leave empty to auto-select 3 AZs)"
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# EKS — Main Node Group
# ---------------------------------------------------------------------------

variable "instance_type" {
  description = "EC2 instance type for the main managed node group"
  type        = string
  default     = "m6i.xlarge"
}

variable "node_min_count" {
  description = "Minimum number of main worker nodes"
  type        = number
  default     = 3
}

variable "node_desired_count" {
  description = "Desired number of main worker nodes"
  type        = number
  default     = 3
}

variable "node_max_count" {
  description = "Maximum number of main worker nodes"
  type        = number
  default     = 10
}

# ---------------------------------------------------------------------------
# EKS — GPU Node Group
# ---------------------------------------------------------------------------

variable "enable_gpu_node_group" {
  description = "Create the GPU managed node group (g4dn.xlarge SPOT)"
  type        = bool
  default     = true
}

variable "gpu_instance_type" {
  description = "EC2 instance type for the GPU node group"
  type        = string
  default     = "g4dn.xlarge"
}

variable "gpu_max_count" {
  description = "Maximum number of GPU worker nodes"
  type        = number
  default     = 3
}

# ---------------------------------------------------------------------------
# RDS PostgreSQL
# ---------------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_name" {
  description = "Name of the initial database created in RDS"
  type        = string
  default     = "omnimedical"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# ElastiCache Redis
# ---------------------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node instance type"
  type        = string
  default     = "cache.t3.micro"
}

# ---------------------------------------------------------------------------
# Monitoring & Backup
# ---------------------------------------------------------------------------

variable "enable_monitoring" {
  description = "Enable detailed monitoring (CloudWatch dashboard, RDS Performance Insights, ALB access logs)"
  type        = bool
  default     = true
}

variable "enable_backup" {
  description = "Enable extended backup retention (30-day RDS, EFS backups, longer S3 lifecycle)"
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# ALB / ACM
# ---------------------------------------------------------------------------

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for the ALB HTTPS listener. Leave empty to skip cert binding."
  type        = string
  default     = ""
}

variable "acm_certificate_domain" {
  description = "Domain name to look up an existing ACM certificate (used when acm_certificate_arn is not set)"
  type        = string
  default     = ""
}
