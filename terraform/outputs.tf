output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.omnimedical.repository_url
}

output "s3_bucket_name" {
  description = "S3 uploads bucket name"
  value       = aws_s3_bucket.uploads.bucket
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = data.aws_eks_cluster.cluster.endpoint
}

output "helm_release_status" {
  description = "Helm release status"
  value       = helm_release.omnimedical.status
}
