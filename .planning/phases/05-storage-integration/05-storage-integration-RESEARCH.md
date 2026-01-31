# Phase 5: Storage Integration - Research

**Researched:** 2026-01-31
**Domain:** AWS EBS (Elastic Block Store) volume operations
**Confidence:** HIGH

## Summary

This research covers the implementation of EBS volume creation and attachment for GPUStack's AWS cloud provider. The key challenge is that **EBS volumes are Availability Zone (AZ) specific** - they must be created in the same AZ as the EC2 instance they will be attached to. This differs from DigitalOcean where volumes are region-scoped.

The implementation requires:
1. Getting the instance's AZ from `describe_instances`
2. Creating the volume in that specific AZ using `create_volume`
3. Attaching the volume using `attach_volume` with proper device naming
4. Validating AZ compatibility before attachment (AWS will reject cross-AZ attachments)

**Primary recommendation:** Always fetch the instance's AZ from describe_instances before creating volumes, and use consistent device naming patterns (/dev/sd[f-p] for HVM instances, /dev/xvd[f-p] for Nitro).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiobotocore | latest | Async AWS SDK | Established pattern in project |
| botocore | 1.34+ | AWS service models | Required by aiobotocore |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| secrets | built-in | Random suffix generation | For unique volume names |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiobotocore | boto3 | aiobotocore is already established in project for async operations |
| gp2 volume type | gp3 | gp3 is newer, but gp2 is default in API; gp3 requires additional IOPS/throughput configuration |

**Installation:**
```bash
# Already installed as part of project dependencies
pip install aiobotocore
```

## Architecture Patterns

### Recommended Implementation Pattern

```python
async def create_volumes_and_attach(
    self, worker_id: int, external_id: str, region: str, *volumes: Volume
) -> List[str]:
    """Create volumes and attach them to the instance."""
    # 1. Get instance details including AZ
    instance = await self.get_instance(external_id)
    if not instance:
        raise RuntimeError(f"Instance {external_id} not found")
    
    # 2. Get instance AZ from describe_instances
    async with self._get_client() as client:
        response = await client.describe_instances(InstanceIds=[external_id])
        az = response['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']
    
    # 3. Create volumes in the same AZ
    volume_ids = []
    for idx, volume in enumerate(volumes):
        # Validate volume spec
        if not volume.size_gb or volume.size_gb <= 0:
            raise ValueError(f"Volume #{idx} missing or invalid 'size_gb': {volume}")
        if not volume.format or volume.format not in ['ext4', 'xfs']:
            raise ValueError(f"Volume #{idx} missing or invalid 'format': {volume}")
        
        # Create volume in instance's AZ
        vol_id = await self._create_volume(
            client, volume, az, worker_id, idx
        )
        volume_ids.append(vol_id)
        
        # Attach volume with proper device name
        await self._attach_volume(client, vol_id, external_id, idx)
    
    return volume_ids
```

### EBS Create Volume Pattern

**What:** Create an EBS volume in a specific AZ with tags
**When to use:** For each volume that needs to be attached to an instance
**Example:**
```python
# Source: AWS CreateVolume API documentation
async def _create_volume(
    self, client, volume: Volume, az: str, worker_id: int, idx: int
) -> str:
    """Create a single EBS volume in the specified AZ."""
    # Generate unique name
    suffix = secrets.token_hex(4)
    name = volume.name or f"gpustack-{worker_id}-{idx}"
    
    response = await client.create_volume(
        AvailabilityZone=az,  # REQUIRED - must match instance AZ
        Size=volume.size_gb,
        VolumeType='gp3',  # or 'gp2' - gp3 is newer default
        Encrypted=True,    # Enable encryption by default
        TagSpecifications=[
            {
                'ResourceType': 'volume',
                'Tags': [
                    {'Key': 'Name', 'Value': name},
                    {'Key': 'ManagedBy', 'Value': 'GPUStack'},
                    {'Key': 'WorkerId', 'Value': str(worker_id)},
                    {'Key': 'VolumeIndex', 'Value': str(idx)},
                    {'Key': 'Format', 'Value': volume.format},
                ]
            }
        ]
    )
    
    volume_id = response['VolumeId']
    
    # Wait for volume to be available
    await client.get_waiter('volume_available').wait(VolumeIds=[volume_id])
    
    return volume_id
```

### EBS Attach Volume Pattern

**What:** Attach an available EBS volume to an EC2 instance
**When to use:** After volume reaches 'available' state
**Example:**
```python
# Source: AWS AttachVolume API documentation
async def _attach_volume(
    self, client, volume_id: str, instance_id: str, idx: int
) -> None:
    """Attach a volume to an instance with proper device naming."""
    # Generate device name based on index
    # HVM instances: /dev/sd[f-p] or /dev/xvd[f-p]
    # Nitro instances: /dev/sd[f-p] (renamed to /dev/nvme* by kernel)
    device_names = ['/dev/sdf', '/dev/sdg', '/dev/sdh', '/dev/sdi', 
                    '/dev/sdj', '/dev/sdk', '/dev/sdl', '/dev/sdm',
                    '/dev/sdn', '/dev/sdo', '/dev/sdp']
    
    if idx >= len(device_names):
        raise ValueError(f"Too many volumes. Maximum supported: {len(device_names)}")
    
    device = device_names[idx]
    
    response = await client.attach_volume(
        VolumeId=volume_id,
        InstanceId=instance_id,
        Device=device
    )
    
    # Wait for attachment to complete
    await client.get_waiter('volume_in_use').wait(VolumeIds=[volume_id])
```

### AZ Detection Pattern

**What:** Get the Availability Zone of an existing EC2 instance
**When to use:** Before creating volumes to ensure AZ compatibility
**Example:**
```python
# Source: AWS DescribeInstances API documentation
async def _get_instance_az(self, client, instance_id: str) -> str:
    """Get the Availability Zone of an EC2 instance."""
    response = await client.describe_instances(InstanceIds=[instance_id])
    
    reservations = response.get('Reservations', [])
    if not reservations:
        raise RuntimeError(f"Instance {instance_id} not found")
    
    instances = reservations[0].get('Instances', [])
    if not instances:
        raise RuntimeError(f"Instance {instance_id} not found")
    
    instance = instances[0]
    placement = instance.get('Placement', {})
    az = placement.get('AvailabilityZone')
    
    if not az:
        raise RuntimeError(f"Could not determine AZ for instance {instance_id}")
    
    return az
```

### Anti-Patterns to Avoid
- **Don't create volumes without specifying AZ:** If you don't specify AvailabilityZone, the operation fails
- **Don't use inconsistent device naming:** Mixing /dev/sd* and /dev/xvd* patterns can cause issues
- **Don't attach without waiting for 'available' state:** Will result in IncorrectState error
- **Don't ignore AZ validation:** Cross-AZ attachment will fail with InvalidVolume.ZoneMismatch

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AZ detection | Custom metadata service | `describe_instances` API | Official API is reliable and consistent |
| Device name tracking | Manual state tracking | Use deterministic pattern (index-based) | AWS doesn't return actual device names consistently |
| Volume state polling | Custom polling loops | `get_waiter('volume_available')` | Built-in waiters handle retry logic and error cases |
| Cross-AZ volume migration | Manual snapshot/copy | Not supported directly - must snapshot and recreate | EBS volumes are fundamentally AZ-bound |

**Key insight:** EBS volumes are AZ-bound resources. Unlike DigitalOcean volumes which can move within a region, EBS volumes are tied to their creation AZ for their entire lifecycle. The only way to "move" a volume to another AZ is to snapshot it and create a new volume from that snapshot in the target AZ.

## Common Pitfalls

### Pitfall 1: Cross-AZ Volume Attachment
**What goes wrong:** Attempting to attach a volume to an instance in a different Availability Zone fails with `InvalidVolume.ZoneMismatch` error.

**Why it happens:** EBS volumes are AZ-specific resources. They can only be attached to instances in the same AZ where they were created.

**How to avoid:** 
1. Always get the instance's AZ before creating volumes
2. Pass the AZ to `create_volume` in the `AvailabilityZone` parameter
3. Validate that volume AZ matches instance AZ before attempting attachment

**Warning signs:** Error message: "The volume 'vol-XXXX' is not in the same availability zone as instance 'i-XXXX'"

### Pitfall 2: Device Name Collisions
**What goes wrong:** Specifying a device name that's already in use on the instance results in `InvalidParameterValue` error.

**Why it happens:** Device names must be unique per instance. Common names like /dev/sdf may already be used by the root volume or other attached volumes.

**How to avoid:**
1. Use a deterministic pattern based on volume index (e.g., /dev/sdf for idx=0, /dev/sdg for idx=1)
2. Check existing block device mappings before choosing device names
3. Use device names starting from /dev/sdf (avoid /dev/sda1 which is typically root)

**Warning signs:** Error message: "The device '/dev/sdX' is already in use on the instance"

### Pitfall 3: Volume Not Available
**What goes wrong:** Attempting to attach a volume before it reaches the 'available' state results in `IncorrectState` error.

**Why it happens:** Volumes start in 'creating' state and transition to 'available'. Attachment can only happen in 'available' state.

**How to avoid:**
1. Always wait for volume to reach 'available' state after creation
2. Use `get_waiter('volume_available')` with appropriate timeout
3. Handle the case where volume creation fails (status becomes 'error')

**Warning signs:** Error message: "Volume is in the 'creating' state, but must be in 'available' state"

### Pitfall 4: Attachment Limit Exceeded
**What goes wrong:** Attempting to attach too many volumes to an instance fails with `AttachmentLimitExceeded` error.

**Why it happens:** Each instance type has a maximum number of EBS volumes it can support (typically 27-39 for Nitro instances).

**How to avoid:**
1. Limit number of volumes per worker to reasonable number (e.g., 4-8)
2. Document the limitation in API docs
3. Provide clear error message if limit exceeded

**Warning signs:** Error message: "AttachmentLimitExceeded"

### Pitfall 5: NVMe Device Name Mismatch
**What goes wrong:** On Nitro-based instances, the device name specified in attach_volume may not match the actual device name seen by the OS.

**Why it happens:** Nitro instances use NVMe devices which are renamed by the kernel (/dev/nvme0n1, /dev/nvme1n1, etc.) independently of the attach request.

**How to avoid:**
1. Document that device names are suggestions, not guarantees on Nitro instances
2. For user data scripts, use `lsblk` or `blkid` to find the actual device
3. Consider using volume tags to identify volumes instead of device names

**Warning signs:** Device specified as /dev/sdf appears as /dev/nvme1n1 in OS

## Code Examples

### Full Implementation Pattern

```python
# Source: AWS API documentation + project patterns
async def create_volumes_and_attach(
    self, worker_id: int, external_id: str, region: str, *volumes: Volume
) -> List[str]:
    """
    Create EBS volumes and attach them to the EC2 instance.
    
    Args:
        worker_id: Internal worker ID for naming and tagging
        external_id: AWS EC2 instance ID (e.g., i-1234567890abcdef0)
        region: AWS region (must match instance region)
        volumes: Volume specifications (size_gb, format, name)
        
    Returns:
        List of AWS EBS volume IDs (e.g., [vol-1234567890abcdef0, ...])
        
    Raises:
        RuntimeError: If instance not found or AWS API errors
        ValueError: If volume specification invalid
    """
    if not volumes:
        return []
    
    async with self._get_client() as client:
        # Get instance AZ
        try:
            response = await client.describe_instances(InstanceIds=[external_id])
            instance = response['Reservations'][0]['Instances'][0]
            az = instance['Placement']['AvailabilityZone']
            instance_state = instance['State']['Name']
        except (IndexError, KeyError, ClientError) as e:
            raise RuntimeError(f"Failed to get instance {external_id} details: {e}")
        
        # Instance must be running or stopped to attach volumes
        if instance_state not in ['running', 'stopped']:
            raise RuntimeError(
                f"Cannot attach volumes to instance in '{instance_state}' state. "
                "Instance must be running or stopped."
            )
        
        volume_ids = []
        for idx, volume in enumerate(volumes):
            # Validate volume spec
            if not volume.size_gb or volume.size_gb <= 0:
                raise ValueError(f"Volume #{idx} invalid size_gb: {volume.size_gb}")
            if not volume.format or volume.format not in ['ext4', 'xfs']:
                raise ValueError(f"Volume #{idx} invalid format: {volume.format}")
            
            # Create volume in same AZ as instance
            vol_id = await self._create_and_attach_volume(
                client, volume, az, worker_id, external_id, idx
            )
            volume_ids.append(vol_id)
        
        return volume_ids

async def _create_and_attach_volume(
    self, client, volume: Volume, az: str, worker_id: int, 
    instance_id: str, idx: int
) -> str:
    """Create a single volume and attach it to the instance."""
    # Generate volume name
    suffix = secrets.token_hex(4)
    name = volume.name or f"gpustack-vol-{worker_id}-{idx}"
    if len(name) > 60:  # AWS volume name limit
        name = name[:60]
    
    # Create volume
    try:
        response = await client.create_volume(
            AvailabilityZone=az,
            Size=volume.size_gb,
            VolumeType='gp3',  # Default to gp3 for better performance
            Encrypted=True,
            TagSpecifications=[
                {
                    'ResourceType': 'volume',
                    'Tags': [
                        {'Key': 'Name', 'Value': name},
                        {'Key': 'ManagedBy', 'Value': 'GPUStack'},
                        {'Key': 'WorkerId', 'Value': str(worker_id)},
                        {'Key': 'VolumeIndex', 'Value': str(idx)},
                        {'Key': 'Format', 'Value': volume.format},
                    ]
                }
            ]
        )
        volume_id = response['VolumeId']
        logger.info(f"Created EBS volume {volume_id} ({volume.size_gb}GB) in {az}")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        raise RuntimeError(f"Failed to create volume: {error_code} - {error_msg}")
    
    # Wait for volume to be available
    try:
        await client.get_waiter('volume_available').wait(
            VolumeIds=[volume_id],
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60}  # 5 min timeout
        )
    except ClientError as e:
        # Clean up on failure
        await self._delete_volume(client, volume_id)
        raise RuntimeError(f"Volume {volume_id} did not become available: {e}")
    
    # Attach volume
    device_names = ['/dev/sdf', '/dev/sdg', '/dev/sdh', '/dev/sdi', 
                    '/dev/sdj', '/dev/sdk', '/dev/sdl', '/dev/sdm',
                    '/dev/sdn', '/dev/sdo', '/dev/sdp']
    if idx >= len(device_names):
        await self._delete_volume(client, volume_id)
        raise ValueError(f"Too many volumes. Maximum: {len(device_names)}")
    
    device = device_names[idx]
    
    try:
        await client.attach_volume(
            VolumeId=volume_id,
            InstanceId=instance_id,
            Device=device
        )
        logger.info(f"Attached volume {volume_id} to {instance_id} as {device}")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        await self._delete_volume(client, volume_id)
        raise RuntimeError(f"Failed to attach volume: {error_code} - {error_msg}")
    
    # Wait for attachment
    try:
        await client.get_waiter('volume_in_use').wait(
            VolumeIds=[volume_id],
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60}
        )
    except ClientError as e:
        logger.warning(f"Timeout waiting for volume {volume_id} attachment: {e}")
        # Don't fail here - attachment may still be in progress
    
    return volume_id

async def _delete_volume(self, client, volume_id: str) -> None:
    """Delete a volume (cleanup helper)."""
    try:
        await client.delete_volume(VolumeId=volume_id)
        logger.info(f"Deleted volume {volume_id}")
    except ClientError as e:
        logger.warning(f"Failed to delete volume {volume_id}: {e}")
```

### Error Handling Pattern

```python
# Error codes to handle specifically
EBS_ERROR_CODES = {
    'InvalidVolume.ZoneMismatch': 
        'Volume and instance are in different Availability Zones',
    'AttachmentLimitExceeded': 
        'Instance has reached the maximum number of attached volumes',
    'InvalidParameterValue': 
        'Device name already in use or invalid',
    'IncorrectState': 
        'Volume is not in available state or instance is not running/stopped',
    'InvalidVolume.NotFound': 
        'Volume does not exist',
    'InvalidInstanceID.NotFound': 
        'Instance does not exist',
}

async def _handle_ebs_error(self, error: ClientError, operation: str) -> RuntimeError:
    """Convert EBS errors to user-friendly messages."""
    error_code = error.response['Error']['Code']
    error_msg = error.response['Error']['Message']
    
    user_message = EBS_ERROR_CODES.get(
        error_code, 
        f"{error_code}: {error_msg}"
    )
    
    logger.error(f"EBS {operation} failed: {error_code} - {error_msg}")
    return RuntimeError(f"EBS {operation} failed: {user_message}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| gp2 default | gp3 default | 2021 (console), 2024 (API behavior) | gp3 offers better baseline performance (3000 IOPS) at lower cost |
| /dev/sd[f-p] naming | /dev/sd[f-p] or /dev/xvd[f-p] | Nitro instances | Nitro uses NVMe which renames devices, but attach API still uses /dev/sd* |
| Unencrypted by default | Encrypted by default (EBS encryption) | 2023+ | AWS recommends encryption for all volumes |
| Wait with time.sleep() | Use get_waiter() | boto3 1.4+ | Built-in waiters handle exponential backoff and error cases |

**Deprecated/outdated:**
- **Standard (magnetic) volumes:** Use gp3 instead - better performance and cost
- **io1 volumes:** io2 is the newer generation with better durability
- **Instance store for persistence:** Only use for temporary/scratch data

## AZ Validation Requirements

**Critical Constraint:** EBS volumes and EC2 instances must be in the same Availability Zone.

**What happens if AZs don't match:**
- `attach_volume` API call fails immediately
- Error code: `InvalidVolume.ZoneMismatch`
- Error message: "The volume 'vol-XXXX' is not in the same availability zone as instance 'i-XXXX'"

**AWS Architecture Details:**
- EBS volumes are AZ-bound network-attached storage
- They cannot be attached to instances in different AZs, even within the same region
- Cross-AZ attachment is fundamentally not supported by AWS infrastructure
- To "move" a volume to another AZ, you must:
  1. Create a snapshot of the volume
  2. Create a new volume from that snapshot in the target AZ
  3. Attach the new volume

**Implementation Implications:**
1. Always get the instance's AZ before creating volumes
2. Pass the AZ explicitly to `create_volume`
3. Do NOT rely on default AZ selection (there is none - AZ is required)
4. Validate instance exists and is in a valid state before volume operations

## Tagging Strategy for EBS Volumes

**Standard Tags (apply to all volumes):**
| Tag Key | Value | Purpose |
|---------|-------|---------|
| Name | `{volume.name}-{worker_id}` or `gpustack-vol-{worker_id}-{idx}` | Human-readable identification |
| ManagedBy | `GPUStack` | Identifies GPUStack-managed resources |
| WorkerId | `{worker_id}` | Links volume to specific worker |
| VolumeIndex | `{idx}` | Identifies volume position in attachment order |
| Format | `{volume.format}` | Filesystem format for user data scripts |

**Optional Tags (based on requirements):**
| Tag Key | Value | Purpose |
|---------|-------|---------|
| CreatedAt | ISO timestamp | Audit trail |
| SizeGB | `{volume.size_gb}` | Quick size reference |
| InstanceId | `{external_id}` | Links volume to specific instance |

**Tagging Best Practices:**
1. **Apply tags at creation time** using `TagSpecifications` parameter - more efficient than tagging after creation
2. **No PII or sensitive data** in tags - tags are visible in billing and many AWS services
3. **Use consistent case** - AWS tags are case-sensitive; stick to TitleCase for keys
4. **Max 50 tags per volume** - well within limits with the proposed strategy
5. **Max 128 chars for keys, 256 for values** - current naming scheme fits easily

## Common EBS Error Codes

| Error Code | Cause | Resolution |
|------------|-------|------------|
| `InvalidVolume.ZoneMismatch` | Volume and instance in different AZs | Create volume in instance's AZ |
| `AttachmentLimitExceeded` | Too many volumes attached to instance | Limit volumes per instance or use larger instance type |
| `InvalidParameterValue` | Device name in use or invalid | Use different device name (e.g., /dev/sdg instead of /dev/sdf) |
| `IncorrectState` | Volume not 'available' or instance not running/stopped | Wait for volume creation or check instance state |
| `InvalidVolume.NotFound` | Volume ID doesn't exist | Verify volume ID, check for eventual consistency |
| `InvalidInstanceID.NotFound` | Instance ID doesn't exist | Verify instance ID, check if recently created |
| `EncryptedVolumesNotSupported` | Instance type doesn't support encryption | Use instance type that supports EBS encryption |
| `VolumeInUse` | Volume already attached to another instance | Detach from current instance first |

## Open Questions

1. **Volume Cleanup on Failure**
   - What we know: If volume creation succeeds but attachment fails, we should clean up
   - What's unclear: Should we retry attachment or fail immediately?
   - Recommendation: Clean up created volumes on any failure to maintain consistency

2. **gp2 vs gp3 Default**
   - What we know: gp3 is newer with better performance; gp2 is API default
   - What's unclear: Does the project have specific performance requirements?
   - Recommendation: Use gp3 for new volumes (better performance/cost ratio)

3. **Encryption Default**
   - What we know: AWS recommends encryption; some older instance types may have issues
   - What's unclear: Does GPUStack have specific encryption requirements?
   - Recommendation: Enable encryption by default (modern GPU instances support it)

## Sources

### Primary (HIGH confidence)
- AWS CreateVolume API Reference: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_CreateVolume.html
- AWS AttachVolume API Reference: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_AttachVolume.html
- AWS DescribeInstances API Reference: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html
- AWS EC2 Error Codes: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/errors-overview.html
- AWS Device Naming Guide: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/device_naming.html
- AWS EBS Volume Types: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html

### Secondary (MEDIUM confidence)
- AWS re:Post - Troubleshooting EBS attachment: https://repost.aws/knowledge-center/ebs-resolve-attach-volume-instance-issue
- AWS EBS User Guide: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-creating-volume.html

### Tertiary (LOW confidence)
- Community blog posts and StackOverflow discussions on EBS patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - using established aiobotocore pattern from project
- Architecture: HIGH - based on official AWS API documentation
- Pitfalls: HIGH - documented error codes are from official AWS documentation

**Research date:** 2026-01-31
**Valid until:** 2026-04-30 (AWS APIs are stable, but new volume types may be introduced)

**Key Takeaways for Implementation:**
1. AZ is **required** for volume creation - must get from instance first
2. Device naming: use /dev/sd[f-p] pattern, avoid /dev/sda-e (root/typical system devices)
3. Always wait for 'available' state before attachment
4. Handle InvalidVolume.ZoneMismatch as a validation error (should never happen if code is correct)
5. Tag volumes at creation time for efficiency
6. Use gp3 volume type for better performance
7. Enable encryption by default
