# Terraform Infrastructure

## Prerequisites
- Terraform >= 1.6
- AWS CLI configured
- kubectl configured for EKS

## Setup
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

## Outputs
- `ecr_repository_url`: ECR repository for Docker images
- `s3_bucket_name`: S3 bucket for document uploads
- `eks_cluster_endpoint`: EKS cluster API endpoint
