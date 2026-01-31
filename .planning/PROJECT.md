# GPUStack AWS Cloud Provider Support

## What This Is

GPUStack is a distributed GPU cluster manager for AI model inference. This project adds AWS EC2 GPU instance support to the existing cloud provider infrastructure, enabling users to deploy GPU workers on AWS alongside the currently supported Digital Ocean provider.

## Core Value

Users can provision and manage GPU-enabled EC2 instances on AWS directly from GPUStack, with the same seamless integration as Digital Ocean.

## Requirements

### Validated

- ✓ Digital Ocean cloud provider integration — existing
- ✓ ProviderClientBase abstract interface — `gpustack/cloud_providers/abstract.py`
- ✓ SSH key management abstraction — existing
- ✓ Cloud instance lifecycle (create/delete/get/wait) — existing
- ✓ Volume attachment support — existing
- ✓ User data template for worker bootstrapping — existing

### Active

- [ ] Implement AWSClient class following ProviderClientBase interface
- [ ] Support EC2 GPU instance families: p3, p4d, g4dn, g5
- [ ] AWS authentication via access key / secret key
- [ ] EC2 instance lifecycle operations (create, delete, describe)
- [ ] SSH key pair management (create, delete, import)
- [ ] EBS volume creation and attachment
- [ ] Wait for instance running state with polling
- [ ] Wait for public IP assignment
- [ ] Proper error handling for AWS API failures
- [ ] Unit tests following existing patterns in `tests/cloud_providers/`
- [ ] Integration with existing cloud provider registration system

### Out of Scope

- Spot instance support — can be added later, focus on on-demand first
- Auto Scaling Groups — complex feature, defer to v2
- VPC/subnet configuration — use default VPC for simplicity
- IAM role integration — access keys sufficient for v1
- Multi-region load balancing — single region deployment for v1

## Context

GPUStack currently supports Digital Ocean as a cloud provider (`gpustack/cloud_providers/digital_ocean.py`). The architecture uses a clean abstraction:

- **Abstract Base**: `ProviderClientBase` defines the interface
- **Instance Lifecycle**: create → wait_for_started → wait_for_public_ip → [attach volumes] → delete
- **Authentication**: Provider-specific credentials (token for DO, access key/secret for AWS)
- **User Data**: Cloud-init script to bootstrap GPUStack worker

AWS implementation will use boto3 (AWS SDK for Python) with async wrapper (aiobotocore) to maintain consistency with the async codebase.

Key AWS services involved:
- EC2: Instance management
- EBS: Volume creation and attachment

## Constraints

- **Tech stack**: Must use Python 3.10+, integrate with existing async codebase
- **AWS SDK**: boto3 or aiobotocore for async support
- **Dependencies**: Add to pyproject.toml, use uv.lock
- **Testing**: pytest with mocking (moto library recommended for AWS mocking)
- **Code style**: Black (88 char), flake8, type hints required
- **Error handling**: Follow existing exception patterns in `gpustack/api/exceptions.py`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use boto3 (sync) vs aiobotocore (async) | aiobotocore for native async, but boto3 with asyncio.to_thread is simpler and sufficient | — Pending |
| Instance families to support | p3 (V100), p4d (A100), g4dn (T4), g5 (A10G) cover common GPU workloads | — Pending |
| AWS region strategy | Single region per cluster for v1, user specifies at creation time | — Pending |

---
*Last updated: 2026-01-31 after initialization*
