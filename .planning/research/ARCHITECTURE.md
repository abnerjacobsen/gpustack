# Architecture Research: AWS Cloud Provider Integration

**Domain:** Multi-cloud GPU cluster management with AWS EC2 integration
**Researched:** 2026-01-31
**Confidence:** HIGH

## Executive Summary

GPUStack currently supports DigitalOcean as a cloud provider using an abstract `ProviderClientBase` interface with a factory pattern. Adding AWS requires a new `AWSClient` implementation that follows the same lifecycle patterns but handles AWS-specific complexity: regions, AZs, AMIs (vs DigitalOcean's simple image slugs), IAM instance profiles, security groups, key pairs, and EBS volumes.

The architecture must maintain consistency with the existing async codebase (asyncio, FastAPI, SQLModel) while accommodating AWS's more complex API surface. The recommended approach uses `aiobotocore` for async AWS SDK operations, following the same abstract class pattern as DigitalOcean.

## Recommended Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GPUStack Server (FastAPI)                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Clusters   │  │   Workers    │  │ Cloud Creds  │              │
│  │    Routes    │  │    Routes    │  │    Routes    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                      │
│  ┌──────▼─────────────────▼──────────────────▼───────┐              │
│  │              Provisioning Controller               │              │
│  │  (Manages worker lifecycle: create → start → IP)   │              │
│  └──────────────────────┬────────────────────────────┘              │
│                         │                                          │
│  ┌──────────────────────▼────────────────────────────┐              │
│  │              Provider Factory (common.py)          │              │
│  │     get_client_from_provider(provider, creds)      │              │
│  └──────────────────────┬────────────────────────────┘              │
│         │                │                │                         │
│  ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼─────────┐                │
│  │ DigitalOcean│ │     AWS     │ │  (Future: GCP  │                │
│  │   Client    │ │   Client    │ │   Azure, etc)  │                │
│  │  (pydo)     │ │(aiobotocore)│ │                │                │
│  └─────────────┘ └─────────────┘ └────────────────┘                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Routes** (clusters, workers, cloud_credentials) | HTTP API endpoints, validation | Controller |
| **Provisioning Controller** | Orchestrates instance lifecycle, manages state transitions | Provider Client, Database |
| **Provider Factory** | Maps ClusterProvider enum to client class + factory function | Provider Clients |
| **AWSClient** | AWS EC2 API operations: run_instances, describe_instances, etc. | aiobotocore, AWS APIs |
| **DigitalOceanClient** | DO API operations (reference implementation) | pydo.Client, DO APIs |
| **UserDataTemplate** | Generates cloud-init scripts for worker bootstrap | Provider Clients (distribution-specific) |

### Data Flow: Instance Creation

```
User Request (Create Worker)
        ↓
Clusters/Workers Routes
        ↓
Provisioning Controller
        ↓
[1] Generate SSH Key Pair (common.py)
        ↓
[2] Get Provider Client via Factory
        ↓
[3] AWSClient.create_ssh_key() → EC2 import_key_pair
        ↓
[4] AWSClient.construct_user_data() → UserDataTemplate (region/AMI specific)
        ↓
[5] AWSClient.create_instance() → EC2 run_instances
        │   • Resolve AMI ID (from image slug/alias)
        │   • Determine subnet/availability zone
        │   • Configure security groups
        │   • Attach IAM instance profile (if GPU instance needs S3, etc.)
        │   • Specify instance type, key pair, user data
        ↓
[6] AWSClient.wait_for_started() → Poll describe_instances
        ↓
[7] AWSClient.wait_for_public_ip() → Poll for public IP assignment
        │   (May need Elastic IP for persistent public IP)
        ↓
[8] AWSClient.create_volumes_and_attach() → EC2 create_volume + attach_volume
        │   • Create EBS volumes
        │   • Attach to instance
        │   • Tag volumes for identification
        ↓
Worker Ready → Register with GPUStack Server
```

### Data Flow: Instance Deletion

```
Delete Worker Request
        ↓
[1] AWSClient.delete_instance() → EC2 terminate_instances
        │   • Terminate instance (this auto-detaches volumes)
        │   • Optional: Delete EBS volumes if configured
        ↓
[2] AWSClient.delete_ssh_key() → EC2 delete_key_pair
        ↓
Cleanup Complete
```

## AWS-Specific Architecture Patterns

### Pattern 1: Async AWS SDK with aiobotocore

**What:** Use `aiobotocore` instead of synchronous `boto3` to maintain consistency with GPUStack's async architecture.

**Why:** GPUStack uses asyncio throughout; mixing sync (boto3) and async code causes blocking issues and breaks FastAPI's async model.

**Implementation:**

```python
from aiobotocore.session import get_session

class AWSClient(ProviderClientBase):
    def __init__(self, access_key: str, secret_key: str, region: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._session = get_session()
    
    async def _get_ec2_client(self):
        """Context manager for EC2 client lifecycle."""
        async with self._session.create_client(
            'ec2',
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        ) as client:
            yield client
```

**Trade-offs:** 
- **Pros:** Native async, non-blocking, consistent with codebase
- **Cons:** Slightly more complex setup, smaller community than boto3

**Confidence:** HIGH - aiobotocore is the standard async AWS SDK, actively maintained (v3.1.1 as of Jan 2026).

### Pattern 2: AMI Resolution Strategy

**What:** DigitalOcean uses simple image slugs (e.g., "ubuntu-20-04-x64"). AWS uses AMI IDs that vary by region.

**Options:**

1. **AMI Alias Map (Recommended)**
   - Map logical names ("ubuntu-22.04-gpu") to AMI IDs per region
   - Store in config or database
   - Allows curated GPU-optimized AMIs

2. **SSM Parameter Resolution**
   - Use AWS Systems Manager public parameters for official AMIs
   - `/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id`
   - Always up-to-date but less control

3. **User-provided AMI ID**
   - Require users to specify AMI ID directly
   - Maximum flexibility but poor UX

**Recommended:** Hybrid approach - provide curated AMI aliases for common GPU workloads, allow override with explicit AMI ID.

```python
# Example AMI resolution
GPU_AMI_MAP = {
    "us-east-1": {
        "ubuntu-22.04-gpu": "ami-0abcdef1234567890",
        "ubuntu-22.04-base": "ami-0987654321fedcba0",
    },
    "us-west-2": {
        "ubuntu-22.04-gpu": "ami-0different123456789",
    }
}

def resolve_ami(image_name: str, region: str) -> str:
    """Resolve logical image name to region-specific AMI ID."""
    if image_name.startswith("ami-"):
        return image_name  # User provided explicit AMI
    return GPU_AMI_MAP.get(region, {}).get(image_name)
```

**Confidence:** HIGH - This is standard practice for multi-region AWS applications.

### Pattern 3: VPC and Network Configuration

**What:** AWS instances require VPC, subnet, and security group configuration. DigitalOcean is simpler (just region).

**Approach:**

| Configuration | DigitalOcean | AWS |
|--------------|--------------|-----|
| Network | Region only | VPC + Subnet (AZ-specific) |
| Firewall | Cloud Firewall (optional) | Security Groups (required) |
| Public IP | Automatic | Optional (enable via subnet auto-assign or Elastic IP) |

**Integration with GPUStack:**

1. **Default VPC:** Use AWS default VPC + default subnet in the specified region
2. **Security Group:** Create/manage a GPUStack-specific security group with required ports
3. **Public IP:** Enable auto-assign public IP on subnet or allocate Elastic IP

```python
# Security group configuration
required_ports = [
    (22, "SSH access"),
    (80, "HTTP (if needed)"),
    (443, "HTTPS (if needed)"),
    (10150, "GPUStack worker port"),  # Check actual port
]

# In AWSClient.create_instance()
sg_id = await self._ensure_security_group_exists()
# run_instances with SecurityGroupIds=[sg_id]
```

**Confidence:** HIGH - AWS networking is well-documented, but requires more configuration than DigitalOcean.

### Pattern 4: SSH Key Management

**What:** DigitalOcean uploads public keys and references by ID. AWS uses key pair names.

**Key Differences:**
- **DigitalOcean:** Upload public key, get numeric ID, reference by ID
- **AWS:** Upload public key with a name, reference by name (not ID)

**Implementation:**

```python
async def create_ssh_key(self, worker_name: str, public_key: str) -> str:
    """Returns key pair name (not ID like DigitalOcean)."""
    key_name = f"gpustack-{worker_name}-{uuid4().hex[:8]}"
    async with self._get_ec2_client() as client:
        await client.import_key_pair(
            KeyName=key_name,
            PublicKeyMaterial=public_key.encode()
        )
    return key_name  # AWS uses name as identifier

async def delete_ssh_key(self, key_name: str):
    """Delete by key name."""
    async with self._get_ec2_client() as client:
        await client.delete_key_pair(KeyName=key_name)
```

**Confidence:** HIGH - Verified with AWS EC2 API documentation.

### Pattern 5: EBS Volume Management

**What:** AWS EBS volumes are separate resources that must be created and attached. DigitalOcean volumes are similar but API differs.

**Lifecycle:**

```python
async def create_volumes_and_attach(
    self, worker_id: int, instance_id: str, region: str, *volumes: Volume
) -> List[str]:
    volume_ids = []
    async with self._get_ec2_client() as client:
        for volume in volumes:
            # Create EBS volume
            resp = await client.create_volume(
                Size=volume.size_gb,
                VolumeType='gp3',  # Good default for GPU workloads
                AvailabilityZone=az,  # Must match instance AZ
                TagSpecifications=[{
                    'ResourceType': 'volume',
                    'Tags': [
                        {'Key': 'Name', 'Value': f'gpustack-{worker_id}'},
                        {'Key': 'gpustack-worker', 'Value': str(worker_id)}
                    ]
                }]
            )
            volume_id = resp['VolumeId']
            
            # Wait for volume available
            await self._wait_for_volume(client, volume_id, 'available')
            
            # Attach to instance
            await client.attach_volume(
                VolumeId=volume_id,
                InstanceId=instance_id,
                Device=f'/dev/xvd{chr(ord('b') + idx)}'  # /dev/xvdb, /dev/xvdc, etc.
            )
            volume_ids.append(volume_id)
    return volume_ids
```

**AWS-Specific Considerations:**
- Volumes are AZ-specific (must match instance AZ)
- Device naming conventions differ by virtualization type
- gp3 volumes recommended for GPU workloads (better IOPS than gp2)

**Confidence:** HIGH - Standard EBS patterns well-documented.

## Project Structure Recommendation

```
gpustack/cloud_providers/
├── __init__.py
├── abstract.py           # Existing - ProviderClientBase
├── common.py             # Existing - factory, SSH key gen
├── user_data.py          # Existing - UserDataTemplate
├── digital_ocean.py      # Existing - reference implementation
└── aws.py                # NEW - AWSClient implementation

gpustack/schemas/
├── clusters.py           # Modify - Add AWS to ClusterProvider enum
└── ...

tests/cloud_providers/
├── test_user_data_template.py
├── test_digital_ocean.py
└── test_aws.py           # NEW - AWS client tests
```

## Build Order (Implementation Phases)

Based on dependencies, implement in this order:

### Phase 1: Foundation (No dependencies)
1. **Add AWS to ClusterProvider enum** (`schemas/clusters.py`)
2. **Create AWSClient shell** (`cloud_providers/aws.py`)
   - Class structure implementing ProviderClientBase
   - __init__ with AWS credentials
   - Stub methods with NotImplementedError

### Phase 2: Core EC2 Operations (Depends on Phase 1)
3. **Implement create_ssh_key / delete_ssh_key**
   - Use EC2 import_key_pair / delete_key_pair
   - Handle AWS key name vs ID difference
4. **Implement create_instance / delete_instance**
   - Use EC2 run_instances / terminate_instances
   - AMI resolution logic
   - Basic security group handling
5. **Implement get_instance / status mapping**
   - Map EC2 instance states to InstanceState enum
   - Extract IP addresses from network interfaces

### Phase 3: Lifecycle Waiting (Depends on Phase 2)
6. **Implement wait_for_started**
   - Poll describe_instances for state == 'running'
   - Handle AWS instance state transitions
7. **Implement wait_for_public_ip**
   - Poll for public IP assignment
   - Consider Elastic IP allocation option

### Phase 4: Storage (Depends on Phase 2)
8. **Implement create_volumes_and_attach**
   - EBS volume creation
   - AZ matching
   - Volume attachment

### Phase 5: User Data & Integration (Depends on all above)
9. **Implement construct_user_data**
   - Override to set distribution based on AMI
   - AWS metadata service URL (169.254.169.254)
10. **Register in factory** (`common.py`)
    - Add AWS entry to factory dict
11. **Add AWS-specific options** (optional)
    - IAM instance profile
    - Spot instances
    - Placement groups

### Phase 6: Testing
12. **Unit tests** with mocked aiobotocore
13. **Integration tests** (manual with real AWS account)

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using Synchronous boto3 in Async Code

**What people do:** Import boto3 and call synchronous methods directly.

**Why it's wrong:** Blocks the event loop, prevents other requests from processing, breaks FastAPI's async model.

**Do this instead:** Use aiobotocore with async/await throughout.

```python
# WRONG - blocks event loop
import boto3
client = boto3.client('ec2')
instance = client.run_instances(...)  # BLOCKING

# RIGHT - non-blocking
import aiobotocore
session = aiobotocore.get_session()
async with session.create_client('ec2') as client:
    instance = await client.run_instances(...)  # ASYNC
```

### Anti-Pattern 2: Hardcoding AMI IDs

**What people do:** Hardcode AMI IDs like "ami-12345678" in code.

**Why it's wrong:** AMI IDs are region-specific and change over time (updates, deprecations).

**Do this instead:** Use AMI aliases with region-specific resolution or SSM parameters.

### Anti-Pattern 3: Ignoring Availability Zones

**What people do:** Create volumes in "the region" without specifying AZ.

**Why it's wrong:** EBS volumes are AZ-specific. Creating a volume without specifying AZ or in wrong AZ prevents attachment.

**Do this instead:** Always capture the instance's AZ during creation and use it for volume creation.

```python
# Get AZ from instance
response = await client.describe_instances(InstanceIds=[instance_id])
az = response['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']

# Use AZ for volume
await client.create_volume(Size=size, AvailabilityZone=az)
```

### Anti-Pattern 4: Leaking AWS Resources on Failure

**What people do:** Create key pair, fail to create instance, don't clean up key pair.

**Why it's wrong:** Orphaned AWS resources cost money and clutter the account.

**Do this instead:** Implement proper cleanup in exception handlers or use context managers.

```python
async def create_instance_with_cleanup(self, ...):
    key_name = None
    try:
        key_name = await self.create_ssh_key(...)
        instance_id = await self.create_instance(...)
        return instance_id
    except Exception:
        if key_name:
            await self.delete_ssh_key(key_name)  # Cleanup
        raise
```

## Scalability Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 GPU instances | Standard on-demand instances, default VPC, manual security groups |
| 10-100 instances | Consider spot instances for cost savings, dedicated security group management |
| 100+ instances | VPC/subnet planning, IAM roles instead of key pairs, placement groups for HPC |

### AWS-Specific Scaling Concerns

1. **API Rate Limits:** AWS EC2 has API rate limits. At scale, implement:
   - Exponential backoff with jitter
   - Request batching where possible
   - Consider using EC2 Fleet API for bulk operations

2. **EBS Volume Limits:** Each instance type has max attachable volumes.
   - Check limits before attempting attachment
   - Consider EBS-optimized instances for GPU workloads

3. **Spot Instances:** For cost savings at scale:
   - Add Spot instance support with interruption handling
   - Use Spot Fleet or EC2 Fleet APIs

## Sources

- [aiobotocore Documentation](https://aiobotocore.readthedocs.io/) - Official async AWS SDK
- [AWS EC2 Boto3 Reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html) - EC2 API operations
- [AWS EC2 User Guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/) - Instance lifecycle, AMIs, EBS
- [DigitalOcean Client Implementation](file:///home/abner/Devel/abnerjacobsen/testes/gpustack/gpustack/cloud_providers/digital_ocean.py) - Reference implementation
- [GPUStack Abstract Base](file:///home/abner/Devel/abnerjacobsen/testes/gpustack/gpustack/cloud_providers/abstract.py) - Interface definition
- [Multi-cloud Architecture Patterns 2025](https://medium.com/@encodedots/favourite-software-architecture-patterns-in-2025-fc1bd74f95fb) - General patterns

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Async SDK (aiobotocore) | HIGH | Official docs, stable v3.x release |
| EC2 Instance Lifecycle | HIGH | AWS docs, standard patterns |
| AMI Resolution | HIGH | Established AWS pattern |
| EBS Volume Management | HIGH | Well-documented, clear API |
| Security Groups/VPC | MEDIUM | More complex than DigitalOcean, but standard |
| Testing Strategy | HIGH | Can follow existing DO test pattern |

## Gaps to Address During Implementation

1. **IAM Instance Profiles:** For production GPU workloads, instances may need S3 access for model storage. Consider adding IAM role support.

2. **Spot Instance Support:** Cost optimization feature - can be added later.

3. **Multi-AZ Support:** Currently worker pools target a region; AWS could support AZ-specific placement.

4. **GPU-Specific AMIs:** Need to curate and maintain GPU-optimized AMI list (NVIDIA drivers, Docker, etc.).

5. **Private Subnet Support:** Current architecture assumes public IPs; private subnets with NAT/bastion would need additional work.

---
*Architecture research for: GPUStack AWS Cloud Provider Integration*
*Researched: 2026-01-31*
