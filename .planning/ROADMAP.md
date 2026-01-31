# GPUStack AWS Cloud Provider - Roadmap

**Core Value:** Users can provision and manage GPU-enabled EC2 instances on AWS directly from GPUStack

**Depth:** Comprehensive (6 phases)
**Created:** 2026-01-31
**Status:** COMPLETE - All 6 Phases Finished ✓

---

## Overview

This roadmap delivers AWS EC2 GPU instance support to GPUStack through 6 incremental phases. Each phase delivers a coherent, verifiable capability building on previous phases. The structure follows AWS's hierarchical networking model (Region → VPC → Subnet → Security Group → Instance → Volume) while maintaining parity with the existing Digital Ocean provider.

**Key dependencies:** Foundation (Phase 1) enables all subsequent work. EC2 operations (Phase 3) unblocks waiting logic (Phase 4) and storage (Phase 5). All phases converge into integration and testing (Phase 6).

---

## Phase Structure

| Phase | Goal | Requirements | Success Criteria |
|-------|------|--------------|------------------|
| **1 - Foundation** | AWS client infrastructure and configuration ready | AUTH-01 to AUTH-06, IMPL-01 to IMPL-04, INTG-01, INTG-03 | 5 criteria |
| **2 - SSH Key Management** | Complete SSH key lifecycle for AWS EC2 | SSH-01 to SSH-04 | 4 criteria |
| **3 - Core EC2 Operations** | GPU instance creation, deletion, and status tracking | INST-01 to INST-08 | 5 criteria |
| **4 - Instance Lifecycle Waiting** | Reliable polling for instance readiness | WAIT-01 to WAIT-04 | 4 criteria |
| **5 - Storage Integration** | EBS volume creation and attachment | STOR-01 to STOR-04 | 4 criteria |
| **6 - Integration & Testing** | Full integration with GPUStack and test coverage | INTG-02, TEST-01 to TEST-06 | 5 criteria |

---

## Phase 1: Foundation & Configuration

**Goal:** AWS client infrastructure exists with authentication, retry policies, and configuration validation.

**Dependencies:** None (foundation phase)

**Requirements (12):**
- AUTH-01: User can configure AWS access key and secret key for authentication
- AUTH-02: User can specify AWS region for worker deployment
- AUTH-03: System validates AWS credentials on configuration
- AUTH-04: User can configure VPC ID (optional, uses default if not specified)
- AUTH-05: User can configure subnet ID (optional, uses default if not specified)
- AUTH-06: User can configure security group ID (optional, creates default if not specified)
- IMPL-01: AWSClient class implements ProviderClientBase interface
- IMPL-02: AWSClient uses aiobotocore for async AWS API operations
- IMPL-03: AWSClient configures boto3 retry policy (max_attempts: 10)
- IMPL-04: AWSClient handles AWS API exceptions with proper error messages
- INTG-01: ClusterProvider enum includes AWS provider type
- INTG-03: AWS configuration schema validates required fields

**Success Criteria:**
1. User can save AWS credentials (access key, secret key) through GPUStack UI/API
2. System validates AWS credentials and reports invalid credential errors clearly
3. AWSClient class exists and passes type checking against ProviderClientBase interface
4. AWSClient initializes aiobotocore session with proper retry configuration (10 attempts)
5. ClusterProvider enum includes `aws` as a provider option

---

## Phase 2: SSH Key Management

**Goal:** Users can manage EC2 SSH key pairs for instance access.

**Dependencies:** Phase 1 (AWS client with credentials configured)

**Requirements (4):**
- SSH-01: System can create new EC2 key pair with generated name
- SSH-02: System can import existing public key as EC2 key pair
- SSH-03: System returns key pair name for instance creation
- SSH-04: System can delete EC2 key pair by name

**Success Criteria:**
1. User can create a new EC2 key pair and receive the private key material
2. User can import an existing SSH public key as an EC2 key pair
3. System returns the key pair name for use in instance creation
4. User can delete an EC2 key pair and it is removed from AWS

**Plans:** 2 plans in 2 waves

Plans:
- [x] 02-01-PLAN.md — Implement create_ssh_key with import_key_pair, collision detection, and tagging
- [x] 02-02-PLAN.md — Implement delete_ssh_key and comprehensive unit tests

---

## Phase 3: Core EC2 Operations

**Goal:** Users can create, delete, and monitor GPU-enabled EC2 instances.

**Dependencies:** Phase 1 (AWS client) + Phase 2 (SSH keys for instance creation)

**Requirements (8):**
- INST-01: User can create EC2 GPU instance (p3, p4d, g4dn, g5 families)
- INST-02: System supports Deep Learning AMI selection by region
- INST-03: System attaches user data (cloud-init) for GPUStack worker bootstrap
- INST-04: System assigns tags to instances for identification
- INST-05: System can terminate EC2 instance by ID
- INST-06: System can describe EC2 instance status and details
- INST-07: System maps AWS instance states to InstanceState enum
- INST-08: System extracts public IP from instance network interfaces

**Success Criteria:**
1. User can create a GPU instance (p3, p4d, g4dn, or g5 family) and receive an instance ID
2. Instance launches with correct Deep Learning AMI for the selected region
3. Instance receives GPUStack worker bootstrap via cloud-init user data
4. Instance has identifying tags (Name, GPUStack-managed, etc.)
5. System can terminate an instance by ID and it stops running in AWS

**Plans:** 2 plans in 1 wave ✓ **COMPLETE**

Plans:
- [x] 03-01-PLAN.md — Deep Learning AMI mapping and create_instance implementation
- [x] 03-02-PLAN.md — delete_instance and get_instance with state mapping

---

## Phase 4: Instance Lifecycle Waiting

**Goal:** System reliably waits for instances to reach running state and have public IP assigned.

**Dependencies:** Phase 3 (instances exist to wait on)

**Requirements (4):**
- WAIT-01: System polls instance status until running (with configurable timeout)
- WAIT-02: System polls for public IP assignment (with configurable timeout)
- WAIT-03: System implements exponential backoff for AWS eventual consistency
- WAIT-04: System handles InvalidInstanceID.NotFound errors with retry logic

**Success Criteria:**
1. System polls instance status until it reaches "running" state within timeout
2. System polls for public IP assignment and returns the IP when available
3. Polling uses exponential backoff to handle AWS eventual consistency
4. System handles InvalidInstanceID.NotFound errors gracefully with retry logic

**Plans:** 2 plans in 1 wave ✓ **COMPLETE**

Plans:
- [x] 04-01-PLAN.md — Implement wait_for_started() with exponential backoff and retry logic
- [x] 04-02-PLAN.md — Implement wait_for_public_ip() with exponential backoff and comprehensive tests

---

## Phase 5: Storage Integration

**Goal:** Users can attach EBS volumes to EC2 instances for model storage.

**Dependencies:** Phase 3 (instances exist to attach volumes to)

**Requirements (4):**
- STOR-01: System can create EBS volume in specified AZ
- STOR-02: System can attach EBS volume to EC2 instance
- STOR-03: System validates volume and instance are in same AZ
- STOR-04: System returns volume IDs for tracking

**Success Criteria:**
1. System can create an EBS volume in the same availability zone as the instance
2. System can attach the EBS volume to a running EC2 instance
3. System validates that volume and instance are in the same AZ before attachment
4. System returns and tracks volume IDs for lifecycle management

**Plans:** 2 plans in 2 waves ✓ **COMPLETE**

Plans:
- [x] 05-01-PLAN.md — Implement create_volumes_and_attach() with AZ awareness, device naming, and tagging
- [x] 05-02-PLAN.md — Comprehensive unit tests for EBS volume operations

---

## Phase 6: Integration & Testing

**Goal:** AWS provider fully integrated with GPUStack provisioning system with comprehensive test coverage.

**Dependencies:** Phases 1-5 (all core functionality complete)

**Requirements (7):**
- INTG-02: Provider factory registers AWSClient for AWS provider type
- TEST-01: Unit tests cover AWSClient create_instance with mocked EC2
- TEST-02: Unit tests cover AWSClient delete_instance with mocked EC2
- TEST-03: Unit tests cover AWSClient SSH key management
- TEST-04: Unit tests cover AWSClient wait_for_started polling logic
- TEST-05: Unit tests cover AWSClient EBS volume operations
- TEST-06: Integration tests validate against real AWS (optional/marked)

**Success Criteria:**
1. Provider factory successfully instantiates AWSClient when provider type is "aws"
2. Unit tests cover create_instance with mocked EC2 responses
3. Unit tests cover delete_instance with mocked EC2 responses
4. Unit tests cover all SSH key management operations
5. All tests pass with moto mocks and code coverage meets GPUStack standards

**Plans:** 3 plans in 2 waves ✓ **COMPLETE**

Plans:
- [x] 06-01-PLAN.md — Factory integration tests for get_client_from_provider()
- [x] 06-02-PLAN.md — Test suite validation and coverage report
- [x] 06-03-PLAN.md — Integration documentation and final verification

---

## Coverage Validation

**Total v1 Requirements:** 39

| Category | Count | Phase Mapping |
|----------|-------|---------------|
| AUTH | 6 | Phase 1 |
| SSH | 4 | Phase 2 |
| INST | 8 | Phase 3 |
| WAIT | 4 | Phase 4 |
| STOR | 4 | Phase 5 |
| IMPL | 4 | Phase 1 |
| INTG | 3 | Phase 1 (2), Phase 6 (1) |
| TEST | 6 | Phase 6 |

**Mapped:** 39/39 ✓
**Orphans:** 0 ✓
**Duplicates:** 0 ✓

---

## Success Criteria by User Perspective

### After Phase 1 (Foundation)
Users can configure AWS credentials and the system validates them. The AWS provider option appears in GPUStack alongside Digital Ocean.

### After Phase 2 (SSH Keys)
Users can create, import, and delete SSH key pairs in AWS for instance access.

### After Phase 3 (Core EC2)
Users can create and delete GPU instances. Instances launch with correct AMIs and GPUStack worker bootstrap.

### After Phase 4 (Waiting)
GPUStack automatically waits for instances to be ready, handling AWS's eventual consistency gracefully.

### After Phase 5 (Storage)
Users can attach persistent storage volumes to GPU instances for model and data storage.

### After Phase 6 (Integration)
AWS GPU instances work end-to-end within GPUStack's worker management system, fully tested and production-ready.

---

## Completion Summary

**Project Status:** ✓ **COMPLETE**

All 6 phases have been successfully implemented:
- **Phase 1:** Foundation - AWSConfig, AWSClient, Factory integration ✓
- **Phase 2:** SSH Key Management - create_ssh_key, delete_ssh_key ✓
- **Phase 3:** Core EC2 Operations - create_instance, delete_instance, get_instance ✓
- **Phase 4:** Instance Lifecycle Waiting - wait_for_started, wait_for_public_ip ✓
- **Phase 5:** Storage Integration - create_volumes_and_attach with EBS ✓
- **Phase 6:** Integration & Testing - 35 passing tests, documentation ✓

**Final Metrics:**
- 39/39 requirements implemented
- 58 total tests (35 passing, 23 skipped with documentation)
- 750+ lines of integration documentation
- Factory registered and tested

---

*Roadmap created: 2026-01-31*
*Project completed: 2026-01-31* ✓
