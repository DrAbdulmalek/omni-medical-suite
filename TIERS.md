# OmniMedical Suite - Tier Comparison

This document explains the differences between the three available tiers of OmniMedical Suite.

## Available Tiers

| Tier | Description | Use Case | Deployment Complexity |
|------|-------------|----------|----------------------|
| Lite | Simple OCR + Basic Correction | Quick testing, simple documents | Low (Single Docker container) |
| Standard | Production OCR with Search | Production use, medium complexity | Medium (Docker Compose) |
| Full | Complete Platform | Enterprise use, full features | High (Kubernetes) |

---

## Feature Comparison

| Feature | Lite | Standard | Full |
|---------|------|----------|------|
| OCR Engine | Tesseract | Ensemble (5 engines) | Ensemble + Custom |
| Languages | English, Arabic | English, Arabic | English, Arabic, French, German |
| Correction | Basic | Advanced | Expert + Context Memory |
| Preprocessing | None | Skew Detection + Auto-Crop | Skew + Auto-Crop + Line Segmentation + Layout Parsing |
| Postprocessing | None | PII Scrubbing + Medical Validation | PII Scrubbing + Medical Validation + Quality Gates |
| Vector Search | No | Yes (Qdrant) | Yes (Qdrant + Hybrid) |
| Output Formats | Text | Text, JSON, CSV | Text, JSON, CSV, XML, PDF |
| Continuous Learning | No | No | Yes |
| Benchmarks | No | No | Yes |
| Training Loop | No | No | Yes |
| Monitoring | No | No | Yes |
| Deployment | Docker | Docker Compose | Kubernetes |
| Containers | 1 | 3 | 5+ |
| Memory | 2GB | 8GB | 16GB |
| Setup Time | 2 min | 5 min | 15 min |
| Max Concurrent | 1 | 4 | 10 |
| Timeout | 30s | 60s | 120s |

---

## Performance Comparison

### Benchmark Results (Test Dataset: 1,000 Medical Documents)

| Metric | Lite | Standard | Full |
|--------|------|----------|------|
| CER (Printed) | 3.2% | 2.8% | 2.5% |
| CER (Handwritten) | 9.1% | 8.5% | 8.0% |
| WER (Printed) | 5.8% | 5.1% | 4.8% |
| WER (Handwritten) | 15.3% | 14.2% | 13.5% |
| Medical Term Accuracy | 91.5% | 94.2% | 95.8% |
| Processing Time | 0.55s/page | 0.45s/page | 0.40s/page |
| Throughput | 1.8 pages/sec | 2.2 pages/sec | 2.5 pages/sec |

### Resource Requirements

| Resource | Lite | Standard | Full |
|----------|------|----------|------|
| CPU | 1 core | 2 cores | 4+ cores |
| RAM | 2GB | 8GB | 16GB |
| Storage | 5GB | 15GB | 30GB |
| GPU | No | Optional | Recommended |

---

## When to Use Each Tier

### Lite Tier

Use when:
- You need simple OCR functionality
- You are testing the system
- You have limited resources
- You only need basic text extraction

Example use cases:
- Extracting text from simple medical documents
- Quick prototyping
- Educational purposes
- Low-resource environments

Command:

    # Using the choose-tier script
    ./choose-tier.sh lite

    # Or directly
    python -m omni_medical_suite --config config/lite.yml

---

### Standard Tier

Use when:
- You need production-quality OCR
- You want vector search capabilities
- You need advanced correction
- You have moderate resources

Example use cases:
- Medical document processing in production
- Searching through medical records
- Batch processing of documents
- Integration with existing systems

Command:

    # Using the choose-tier script (default)
    ./choose-tier.sh standard

    # Or directly
    python -m omni_medical_suite --config config/standard.yml

---

### Full Tier

Use when:
- You need the complete platform
- You want continuous learning
- You need benchmarks and monitoring
- You have sufficient resources

Example use cases:
- Enterprise medical document processing
- Continuous improvement of models
- Quality assurance and monitoring
- Large-scale deployments

Command:

    # Using the choose-tier script
    ./choose-tier.sh full

    # Or directly
    python -m omni_medical_suite --config config/full.yml

---

## Migration Between Tiers

You can easily migrate between tiers by changing the configuration file:

1. Upgrade from Lite to Standard:

    # Stop Lite
    docker stop omni-lite
    
    # Start Standard
    docker-compose -f docker-compose-standard.yml up -d

2. Upgrade from Standard to Full:

    # Stop Standard
    docker-compose -f docker-compose-standard.yml down
    
    # Start Full (requires Kubernetes)
    kubectl apply -f k8s-full/

3. Downgrade from Full to Standard:

    # Stop Full
    kubectl delete -f k8s-full/
    
    # Start Standard
    docker-compose -f docker-compose-standard.yml up -d

---

## Configuration Files

Each tier has its own configuration file in the config/ directory:

- Lite: config/lite.yml
- Standard: config/standard.yml
- Full: config/full.yml

You can customize these files to fine-tune the behavior of each tier.

---

## Custom Tiers

You can create your own custom tier by:

1. Creating a new YAML file in the config/ directory
2. Defining your components and settings
3. Running with your custom config:

    python -m omni_medical_suite --config config/my-custom-tier.yml

---

## Support

For questions or issues with a specific tier:
- Lite Tier: Open an issue with the [tier:lite] label
- Standard Tier: Open an issue with the [tier:standard] label
- Full Tier: Open an issue with the [tier:full] label

For general questions, use the [tier:general] label.
