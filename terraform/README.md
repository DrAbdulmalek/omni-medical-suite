# OmniMedical Suite — AWS EKS Terraform Infrastructure

## Prerequisites

| Tool | Version |
|------|---------|
| Terraform | >= 1.5 |
| AWS CLI | >= 2.0 |
| `kubectl` | >= 1.28 |
| `helm` | >= 3.12 |

Ensure your AWS credentials are configured (`aws configure` or environment variables).

## Quick Start

```bash
cd terraform/

# 1. Copy and customise variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars as needed

# 2. Initialise providers and modules
terraform init

# 3. Review the execution plan
terraform plan -out=tfplan

# 4. Apply the infrastructure
terraform apply tfplan
```

## Configure kubectl

Terraform prints the command after apply. Use it directly:

```bash
aws eks update-kubeconfig --name omnimedical-suite --region us-east-1

# Verify connectivity
kubectl get nodes
kubectl get svc
```

## Key Outputs

| Output | Description |
|--------|-------------|
| `cluster_endpoint` | EKS API server URL |
| `configure_kubectl` | Ready-to-run kubectl config command |
| `rds_endpoint` | PostgreSQL connection endpoint |
| `redis_endpoint` | Redis primary endpoint |
| `alb_dns_name` | Application Load Balancer DNS name |
| `s3_bucket_names` | Document, backup, and log bucket names |
| `kms_key_arn` | KMS encryption key ARN |
| `api_irsa_role_arn` | IAM role for API pods (IRSA) |
| `efs_dns_name` | EFS mount DNS for shared model cache |

View all outputs:

```bash
terraform output
```

## Architecture

```
Internet
  │
  ▼
┌──────────┐     ┌──────────────────────────────────────────────┐
│  Route53  │───▶ │               Public Subnets                 │
│  (ACM)    │     │  ┌────────────────┐   ┌───────────────────┐ │
└──────────┘     │  │  ALB (443/80)   │   │  NAT Gateway ×3    │ │
                 │  └───────┬────────┘   └───────────────────┘ │
                 │          │                                   │
                 └──────────┼───────────────────────────────────┘
                            │
                 ┌──────────┼───────────────────────────────────┐
                 │          ▼       Private Subnets (3 AZs)     │
                 │  ┌──────────────────────────────────────┐   │
                 │  │         EKS Cluster (v1.29)          │   │
                 │  │  ┌──────────────┐ ┌───────────────┐  │   │
                 │  │  │ Main Nodes   │ │ GPU Nodes     │  │   │
                 │  │  │ m6i.xlarge×3 │ │ g4dn.xlarge  │  │   │
                 │  │  │ (ON_DEMAND)  │ │ (SPOT, opt.)  │  │   │
                 │  │  └──────────────┘ └───────────────┘  │   │
                 │  └──────────────────────────────────────┘   │
                 │                                             │
                 │  ┌─────────────────┐  ┌──────────────────┐  │
                 │  │ RDS PostgreSQL  │  │ ElastiCache      │  │
                 │  │ db.t3.medium    │  │ Redis 7.0        │  │
                 │  │ Multi-AZ, enc.  │  │ cache.t3.micro   │  │
                 │  └─────────────────┘  └──────────────────┘  │
                 │                                             │
                 │  ┌─────────────────┐  ┌──────────────────┐  │
                 │  │ EFS (model      │  │ S3 Buckets       │  │
                 │  │ cache, NFS)     │  │ docs + backups   │  │
                 │  └─────────────────┘  └──────────────────┘  │
                 │                                             │
                 └─────────────────────────────────────────────┘
                                   VPC (10.0.0.0/16)
```

## Tearing Down

```bash
terraform destroy
```

> **Note:** RDS deletion protection is enabled. Run `terraform destroy -target=module.db` first or disable protection manually.

## SSL/TLS for the ALB

1. Request an ACM certificate (in `us-east-1` for ALB) or import one.
2. Set `acm_certificate_arn` in `terraform.tfvars`.
3. `terraform apply` — the HTTPS listener will bind the certificate.

## GPU Workloads

GPU nodes have the taint `nvidia.com/gpu=present:NoSchedule`. Pods requesting GPUs must include a matching toleration:

```yaml
tolerations:
  - key: "nvidia.com/gpu"
    operator: "Equal"
    value: "present"
    effect: "NoSchedule"
```

## Cost Estimate (us-east-1, on-demand, monthly)

| Resource | Approx. Cost |
|----------|-------------|
| EKS cluster control plane | $73 |
| 3 × m6i.xlarge | $309 |
| RDS db.t3.medium Multi-AZ | $84 |
| ElastiCache cache.t3.micro ×3 | $14 |
| NAT Gateway ×3 + data | $45 |
| ALB | $22 |
| S3 (~100 GB) | $3 |
| EFS (~50 GB) | $7 |
| **Estimated total** | **~$557/mo** |

GPU nodes (g4dn.xlarge SPOT) add ~$0.524/hr when running.
