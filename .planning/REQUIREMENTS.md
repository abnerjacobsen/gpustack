# Requirements: GPUStack AWS Cloud Provider

**Defined:** 2026-01-31
**Core Value:** Users can provision and manage GPU-enabled EC2 instances on AWS directly from GPUStack

## v1 Requirements

### Authentication & Configuration

- [ ] **AUTH-01**: User can configure AWS access key and secret key for authentication
- [ ] **AUTH-02**: User can specify AWS region for worker deployment
- [ ] **AUTH-03**: System validates AWS credentials on configuration
- [ ] **AUTH-04**: User can configure VPC ID (optional, uses default if not specified)
- [ ] **AUTH-05**: User can configure subnet ID (optional, uses default if not specified)
- [ ] **AUTH-06**: User can configure security group ID (optional, creates default if not specified)

### SSH Key Management

- [ ] **SSH-01**: System can create new EC2 key pair with generated name
- [ ] **SSH-02**: System can import existing public key as EC2 key pair
- [ ] **SSH-03**: System returns key pair name for instance creation
- [ ] **SSH-04**: System can delete EC2 key pair by name

### Instance Management

- [ ] **INST-01**: User can create EC2 GPU instance (p3, p4d, g4dn, g5 families)
- [ ] **INST-02**: System supports Deep Learning AMI selection by region
- [ ] **INST-03**: System attaches user data (cloud-init) for GPUStack worker bootstrap
- [ ] **INST-04**: System assigns tags to instances for identification
- [ ] **INST-05**: System can terminate EC2 instance by ID
- [ ] **INST-06**: System can describe EC2 instance status and details
- [ ] **INST-07**: System maps AWS instance states to InstanceState enum
- [ ] **INST-08**: System extracts public IP from instance network interfaces

### Instance Lifecycle Waiting

- [ ] **WAIT-01**: System polls instance status until running (with configurable timeout)
- [ ] **WAIT-02**: System polls for public IP assignment (with configurable timeout)
- [ ] **WAIT-03**: System implements exponential backoff for AWS eventual consistency
- [ ] **WAIT-04**: System handles InvalidInstanceID.NotFound errors with retry logic

### Storage (EBS Volumes)

- [ ] **STOR-01**: System can create EBS volume in specified AZ
- [ ] **STOR-02**: System can attach EBS volume to EC2 instance
- [ ] **STOR-03**: System validates volume and instance are in same AZ
- [ ] **STOR-04**: System returns volume IDs for tracking

### Client Implementation

- [ ] **IMPL-01**: AWSClient class implements ProviderClientBase interface
- [ ] **IMPL-02**: AWSClient uses aiobotocore for async AWS API operations
- [ ] **IMPL-03**: AWSClient configures boto3 retry policy (max_attempts: 10)
- [ ] **IMPL-04**: AWSClient handles AWS API exceptions with proper error messages

### Integration & Registration

- [ ] **INTG-01**: ClusterProvider enum includes AWS provider type
- [ ] **INTG-02**: Provider factory registers AWSClient for AWS provider type
- [ ] **INTG-03**: AWS configuration schema validates required fields

### Testing

- [ ] **TEST-01**: Unit tests cover AWSClient create_instance with mocked EC2
- [ ] **TEST-02**: Unit tests cover AWSClient delete_instance with mocked EC2
- [ ] **TEST-03**: Unit tests cover AWSClient SSH key management
- [ ] **TEST-04**: Unit tests cover AWSClient wait_for_started polling logic
- [ ] **TEST-05**: Unit tests cover AWSClient EBS volume operations
- [ ] **TEST-06**: Integration tests validate against real AWS (optional/marked)

## v2 Requirements (Deferred)

### Cost Optimization

- **COST-01**: Support Spot Instance requests with interruption handling
- **COST-02**: Implement Spot Instance interruption notices (2-minute warning)
- **COST-03**: Display Spot Instance pricing vs On-Demand pricing
- **COST-04**: Auto-replace interrupted Spot workers

### Advanced Instance Management

- **INST-09**: Support instance family selection based on GPU requirements
- **INST-10**: Support custom AMIs (user-provided AMI IDs)
- **INST-11**: Support instance profile/IAM role attachment
- **INST-12**: Support placement groups for low-latency networking

### Networking

- **NET-01**: Support private subnet deployment with NAT gateway
- **NET-02**: Support Elastic IP assignment
- **NET-03**: Support multiple Availability Zones
- **NET-04**: Cross-AZ worker deployment for resilience

### Monitoring

- **MON-01**: AWS CloudWatch integration for instance metrics
- **MON-02**: Cost estimation before instance creation
- **MON-03**: AWS billing alerts integration

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto Scaling Groups | Requires scheduler integration; complex feature for v2+ |
| Windows instances | Linux-only for v1; Windows adds complexity |
| Inferentia/Trainium chips | Different architecture than CUDA GPUs; defer to v2 |
| Outposts/Wavelength | Enterprise edge features; not core to GPUStack value |
| Multi-region load balancing | Single region per cluster for v1 simplicity |
| Container orchestration (ECS/EKS) | GPUStack manages bare EC2, not containers |
| Reserved Instance management | Cost optimization feature; defer to v2 |
| AWS Organizations support | Multi-account support; not needed for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Pending |
| AUTH-02 | Phase 1 | Pending |
| AUTH-03 | Phase 1 | Pending |
| AUTH-04 | Phase 1 | Pending |
| AUTH-05 | Phase 1 | Pending |
| AUTH-06 | Phase 1 | Pending |
| SSH-01 | Phase 2 | Pending |
| SSH-02 | Phase 2 | Pending |
| SSH-03 | Phase 2 | Pending |
| SSH-04 | Phase 2 | Pending |
| INST-01 | Phase 2 | Pending |
| INST-02 | Phase 2 | Pending |
| INST-03 | Phase 2 | Pending |
| INST-04 | Phase 2 | Pending |
| INST-05 | Phase 2 | Pending |
| INST-06 | Phase 2 | Pending |
| INST-07 | Phase 2 | Pending |
| INST-08 | Phase 2 | Pending |
| WAIT-01 | Phase 3 | Pending |
| WAIT-02 | Phase 3 | Pending |
| WAIT-03 | Phase 3 | Pending |
| WAIT-04 | Phase 3 | Pending |
| STOR-01 | Phase 4 | Pending |
| STOR-02 | Phase 4 | Pending |
| STOR-03 | Phase 4 | Pending |
| STOR-04 | Phase 4 | Pending |
| IMPL-01 | Phase 1 | Pending |
| IMPL-02 | Phase 1 | Pending |
| IMPL-03 | Phase 1 | Pending |
| IMPL-04 | Phase 1 | Pending |
| INTG-01 | Phase 1 | Pending |
| INTG-02 | Phase 5 | Pending |
| INTG-03 | Phase 1 | Pending |
| TEST-01 | Phase 5 | Pending |
| TEST-02 | Phase 5 | Pending |
| TEST-03 | Phase 5 | Pending |
| TEST-04 | Phase 5 | Pending |
| TEST-05 | Phase 5 | Pending |
| TEST-06 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-31*
