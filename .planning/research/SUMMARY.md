# Project Research Summary

**Project:** AWS EC2 GPU Integration for GPUStack
**Domain:** Cloud GPU Worker Management (AWS EC2)
**Researched:** 2026-01-31
**Confidence:** HIGH

## Executive Summary

GPUStack is extending its cloud provider support to include AWS EC2 GPU instances, following the existing DigitalOcean integration pattern. AWS presents significantly more complexity than DigitalOcean due to its hierarchical networking model (VPC/Subnet/Security Group), AMI-based image selection (vs simple image slugs), and the eventual consistency of its EC2 API.

Based on comprehensive research across technology stack, features, architecture, and common pitfalls, **aiobotocore 3.1.1** is the definitive choice for async AWS SDK operations. It provides native async AWS API access with full EC2, EBS, and IAM coverage while maintaining consistency with GPUStack's existing async codebase (asyncio, FastAPI, SQLModel).

The primary risks center on AWS's operational complexity: eventual consistency can cause race conditions during instance creation, rate limiting requires careful client configuration, and IAM permission scoping must be precise to avoid both security vulnerabilities and operational failures. The recommended approach implements the AWS client in 5-6 incremental phases, starting with core EC2 operations and progressively adding storage, networking, and advanced features like Spot instances.

## Key Findings

### Recommended Stack

**aiobotocore 3.1.1** is the definitive choice for AWS EC2 integration. It provides native async AWS SDK access with full EC2, EBS, and IAM API coverage, directly mirroring the official boto3 API structure while maintaining async compatibility with GPUStack's FastAPI architecture. The library is actively maintained (latest release Jan 20, 2026), part of the well-established aio-libs ecosystem, and is the standard async replacement for synchronous boto3 code.

Use `aiobotocore` directly (not `aioboto3`) because GPUStack's cloud provider abstraction only needs low-level client operations (instance lifecycle, volume management, SSH key CRUD) rather than high-level boto3 resource abstractions.

**Core technologies:**
- **aiobotocore ^3.1.1**: Async AWS SDK client for EC2, EBS, IAM operations — Official async implementation of botocore; 1:1 API parity with boto3; actively maintained by aio-libs organization
- **types-aiobotocore[essential] ^2.15.0**: Type stubs for IDE autocomplete and mypy checking
- **moto[ec2]**: AWS service mocking for unit tests — enables testing without real AWS credentials
- **pytest-asyncio >=0.23.0**: Async test runner with AnyIO compatibility

### Expected Features

**Must have (table stakes) — 11 features for MVP:**
1. **AWS Credentials (Access Key/Secret)** — Required for all AWS API calls
2. **Region Selection** — AWS has 30+ regions; users need control over data locality
3. **VPC/Subnet Selection** — Required for instance creation; default VPC acceptable for MVP
4. **Security Group Configuration** — Required for worker-server communication
5. **SSH Key Management** — Pattern from DO; required for worker access
6. **Instance Creation/Deletion** — Core functionality; parity with DO
7. **Instance Type Selection (G4dn, G5, P3, P4de, P5)** — Core GPU families for inference
8. **AMI Selection (pre-validated list)** — Deep Learning AMI or Ubuntu with NVIDIA drivers
9. **Wait for Instance Start + Public IP** — Pattern from DO; required for provisioning flow
10. **Worker Pool Management** — Core GPUStack abstraction; apply to AWS
11. **Volume Attachment (EBS)** — Pattern from DO; model storage requirement

**Should have (differentiators) — P2 priority:**
- **Spot Instance Support** — 60-90% cost savings; major differentiator for AI workloads (HIGH complexity)
- **Instance Family Flexibility** — Auto-select from G4/G5/P3/P4/P5 based on model requirements
- **Availability Zone Awareness** — Cross-AZ deployment for resilience; critical for Spot
- **AMI Optimization (custom GPUStack AMI)** — Faster boot times vs cloud-init bootstrap
- **Instance Health Checks & Auto-recovery** — Replace failed workers automatically
- **Cost Estimation & Budget Alerts** — AWS pricing API integration

**Defer (v2+):**
- **Auto-scaling Based on Queue Depth** — Requires scheduler integration; complex
- **Placement Groups for Multi-GPU** — Required for H100/H200 multi-node distributed training
- **Elastic Fabric Adapter (EFA) Support** — Complex networking; P4d/P5 only
- **Reserved Instance/On-Demand Hybrid** — Financial complexity; user can manage

### Architecture Approach

The architecture follows GPUStack's existing `ProviderClientBase` abstraction with a factory pattern. A new `AWSClient` implementation will handle AWS-specific complexity (regions, AZs, AMIs, IAM instance profiles, security groups, key pairs, EBS volumes) while maintaining consistency with the async codebase.

**Major components:**
1. **Routes** (clusters, workers, cloud_credentials) — HTTP API endpoints, validation
2. **Provisioning Controller** — Orchestrates instance lifecycle, manages state transitions
3. **Provider Factory** (`common.py`) — Maps ClusterProvider enum to client class
4. **AWSClient** (`aws.py`) — AWS EC2 API operations: run_instances, describe_instances, etc.
5. **UserDataTemplate** — Generates cloud-init scripts for worker bootstrap (region/AMI specific)

**Key patterns:**
- **Async AWS SDK with aiobotocore** — Must use `async with` context managers (breaking change in v3.x)
- **AMI Resolution Strategy** — Map logical names to region-specific AMI IDs, allow explicit override
- **VPC and Network Configuration** — Use default VPC + default subnet, create GPUStack-specific security group
- **SSH Key Management** — AWS uses key pair names (not IDs like DigitalOcean)
- **EBS Volume Management** — Create in same AZ as instance, use gp3 volumes

### Critical Pitfalls

Based on official AWS documentation and community patterns:

1. **Ignoring Eventual Consistency** — AWS EC2 API follows eventual consistency. After `RunInstances`, the resource ID may not be immediately visible, causing `InvalidInstanceID.NotFound` errors. **Prevention:** Always use exponential backoff when checking resource state; use boto3 waiters with 15-second intervals.

2. **Underestimating AWS Rate Limiting** — EC2 API has unpublished rate limits. Polling too frequently causes `RequestLimitExceeded`. **Prevention:** Configure retry settings (max_attempts: 10, mode: 'standard'), implement client-side rate limiting with jitter, cache Describe results.

3. **Inadequate IAM Permission Scoping** — `RunInstances` requires permissions on AMI, instance, subnet, security group, key pair, AND volume. **Prevention:** Document minimum required permissions, test with restricted role (not admin), use IAM policy simulator.

4. **Improper Async SDK Patterns** — Creating new boto3 client per request or not awaiting properly causes event loop blocking. **Prevention:** Initialize clients once and reuse, use proper async context managers (`async with`), configure AioConfig for retries.

5. **Wrong GPU Instance Type / AMI Combinations** — Deep Learning AMIs have different driver support (Proprietary vs OSS). G4dn was removed from proprietary driver support in March 2024. **Prevention:** Maintain compatibility matrix, validate AMI before launch, test GPU accessibility with `nvidia-smi`.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation
**Rationale:** Core abstractions and AWS client setup must be in place before any EC2 operations. Following the dependency chain: Credentials → Region → VPC → Subnet → Security Group → Instance.

**Delivers:**
- AWS added to ClusterProvider enum
- AWSClient shell implementing ProviderClientBase
- aiobotocore integration with proper async context managers
- Basic IAM permission documentation

**Addresses features:** AWS Credentials, Region Selection, VPC/Subnet Selection (default), Security Group Configuration

**Avoids pitfalls:** Improper Async SDK Patterns, Inadequate IAM Permission Scoping

**Research flag:** Standard patterns — aiobotocore usage is well-documented; skip additional research.

### Phase 2: Core EC2 Operations
**Rationale:** Instance lifecycle is the foundation; SSH keys and basic networking must work before adding storage or advanced features.

**Delivers:**
- SSH Key Management (import_key_pair / delete_key_pair)
- Instance Creation/Deletion (run_instances / terminate_instances)
- AMI resolution logic with region-specific mapping
- Instance status mapping to GPUStack's InstanceState enum

**Addresses features:** SSH Key Management, Instance Creation/Deletion, Instance Type Selection, AMI Selection, Wait for Instance Start, Wait for Public IP

**Avoids pitfalls:** Ignoring Eventual Consistency, Wrong GPU Instance Type / AMI Combinations

**Research flag:** Needs validation — AMI compatibility matrix needs testing with actual GPU instances; IAM permissions need verification with restricted role.

### Phase 3: Storage Integration
**Rationale:** EBS volumes are AZ-specific and must match instance AZ. This builds on Phase 2's instance creation capabilities.

**Delivers:**
- EBS volume creation and attachment
- AZ-aware volume placement
- Volume tagging for identification

**Addresses features:** Volume Attachment

**Avoids pitfalls:** EBS Volume Attachment (wait for "available" state, AZ matching)

**Research flag:** Standard patterns — EBS attachment patterns are well-documented.

### Phase 4: Worker Pool & Integration
**Rationale:** Worker pools aggregate the previous phases; factory registration connects AWS to GPUStack's provisioning controller.

**Delivers:**
- Worker Pool Management for AWS
- Factory registration in common.py
- construct_user_data implementation (AWS metadata service)
- End-to-end provisioning flow

**Addresses features:** Worker Pool Management

**Avoids pitfalls:** Resource cleanup on failure (orphaned keys/volumes)

**Research flag:** Standard patterns — follows existing DO pattern.

### Phase 5: Testing & Hardening
**Rationale:** AWS integration requires thorough testing due to complexity and cost implications.

**Delivers:**
- Unit tests with mocked aiobotocore (moto)
- Integration tests with real AWS account
- IAM permission validation
- Rate limiting and retry configuration verification

**Avoids pitfalls:** All Phase 1-4 pitfalls through testing

**Research flag:** Needs validation — Real AWS testing required; rate limiting behavior needs load testing.

### Phase 6: Cost Optimization (P2 Features)
**Rationale:** Spot instances and cost features add significant complexity; defer until core is stable.

**Delivers:**
- Spot Instance Support with interruption handling
- Instance Family Flexibility (fallback types)
- Availability Zone Awareness (multi-AZ for Spot)
- Cost Estimation integration

**Addresses features:** Spot Instance Support, Instance Family Flexibility, AZ Awareness, Cost Estimation

**Avoids pitfalls:** Spot capacity planning, placement group conflicts

**Research flag:** Needs research — Spot instance patterns, interruption handling, and capacity monitoring need deeper investigation during planning.

### Phase Ordering Rationale

- **Dependencies drive order:** AWS networking is hierarchical (Region → VPC → Subnet → Security Group → Instance). Volumes are AZ-specific and require instance placement first.
- **Risk mitigation:** Core EC2 operations (Phase 2) include all critical pitfalls (eventual consistency, rate limiting, AMI compatibility). These must be validated before building on top.
- **Cost considerations:** Testing with real AWS (Phase 5) should happen before adding expensive features like Spot instances (Phase 6) to avoid wasted resources during iteration.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Core EC2):** AMI compatibility matrix for GPU instances needs validation; IAM minimum permissions need testing with restricted role
- **Phase 5 (Testing):** Real AWS integration testing patterns; moto limitations for complex scenarios
- **Phase 6 (Cost Optimization):** Spot instance interruption handling; capacity pool monitoring; best practices for GPU workloads

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** aiobotocore patterns well-documented; factory pattern exists
- **Phase 3 (Storage):** EBS attachment patterns are standard AWS
- **Phase 4 (Integration):** Follows existing DigitalOcean pattern closely

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | aiobotocore is official, well-maintained; v3.1.1 stable; clear choice over alternatives |
| Features | MEDIUM | Feature list comprehensive but needs GPUStack-specific validation; some features inferred from DO parity |
| Architecture | HIGH | Clear pattern from existing DigitalOceanClient; aiobotocore architecture well-documented |
| Pitfalls | HIGH | Based on official AWS documentation, community patterns, and established best practices |

**Overall confidence:** HIGH

The research provides a solid foundation for implementation. The technology choice (aiobotocore) is clear and correct. The architecture follows established GPUStack patterns. The main uncertainty is in feature prioritization (MEDIUM confidence) which will be resolved during implementation planning with GPUStack maintainers.

### Gaps to Address

1. **AMI Maintenance Strategy:** Research recommends curated AMI aliases but doesn't define the maintenance process for keeping AMI IDs current across regions. **Handle during planning:** Define AMI update process; consider SSM parameter resolution as alternative.

2. **GPU Instance Validation:** Compatibility matrix between instance types (G4dn, G5, P3, P4de, P5) and AMIs needs real-world testing. **Handle during Phase 2:** Launch each supported instance type, verify GPU accessibility with `nvidia-smi`.

3. **IAM Permission Boundaries:** Minimum permissions documented but need validation with actual restricted role. **Handle during Phase 1:** Create test IAM role with documented permissions, run full test suite.

4. **Cost Estimation API:** AWS pricing API is complex; research doesn't provide implementation details. **Handle during Phase 6:** Dedicated research on AWS Price List API integration.

5. **Private Subnet Support:** Current architecture assumes public IPs for workers. Private subnets with NAT/bastion hosts would need additional work. **Handle post-MVP:** Document as future enhancement.

## Sources

### Primary (HIGH confidence)
- aiobotocore Documentation (aiobotocore.aio-libs.org) — Official async SDK patterns, v3.x breaking changes
- aiobotocore PyPI 3.1.1 (pypi.org) — Version confirmation, dependency compatibility
- AWS EC2 Eventual Consistency Documentation (docs.aws.amazon.com) — Official AWS consistency model
- AWS SDK Retry Behavior (docs.aws.amazon.com) — Retry modes and throttling
- AWS EC2 User Guide (docs.aws.amazon.com) — Instance lifecycle, AMIs, EBS patterns
- GPUStack DigitalOcean Integration (docs.gpustack.ai) — Reference implementation patterns

### Secondary (MEDIUM confidence)
- AWS DLAMI Release Notes — GPU instance type support matrix, driver compatibility
- AWS Spot Best Practices — Spot instance patterns (general, not GPUStack-specific)
- AWS Cost Optimization Blog — GPU cost optimization strategies
- Moto EC2 Testing Documentation — Testing patterns for AWS integration

### Tertiary (LOW confidence / Validation needed)
- GPUStack codebase inspection (digital_ocean.py, abstract.py, common.py) — Current implementation patterns (may have evolved)
- Community forums / Stack Overflow — Specific error patterns and workarounds

---

*Research completed: 2026-01-31*
*Ready for roadmap: yes*
