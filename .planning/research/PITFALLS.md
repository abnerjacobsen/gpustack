# Domain Pitfalls: AWS EC2 Integration for GPUStack

**Domain:** AWS EC2 GPU Worker Integration
**Researched:** 2026-01-31
**Confidence:** HIGH (based on official AWS documentation + community patterns)

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

---

### Pitfall 1: Ignoring Eventual Consistency

**What goes wrong:**
Immediately querying for an instance after `RunInstances` returns `InvalidInstanceID.NotFound`. Similarly, attempting to attach an EBS volume or modify a security group right after creation fails because the resource hasn't propagated through AWS's distributed systems.

**Why it happens:**
The EC2 API follows an eventual consistency model. After a successful API call (e.g., `RunInstances`), the resource ID may not be immediately visible to subsequent commands. AWS documentation states this can take "a few seconds up to a few minutes" in some cases.

**Consequences:**
- Workers appear to fail creation when they actually succeeded
- Integration tests become flaky and unreliable
- Race conditions in production cause worker provisioning failures
- Duplicate instance launches when retry logic doesn't handle consistency properly

**Prevention:**
1. **Always use exponential backoff** when checking resource state after creation:
   ```python
   # Wait using built-in boto3 waiters (already implement backoff)
   waiter = ec2.get_waiter('instance_running')
   waiter.wait(InstanceIds=[instance_id])
   
   # Or implement custom exponential backoff
   for attempt in range(max_retries):
       try:
           response = ec2.describe_instances(InstanceIds=[instance_id])
           if response['Reservations']:
               break
       except ClientError as e:
           if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
               sleep(min(2 ** attempt, 60))  # Cap at 60 seconds
               continue
           raise
   ```

2. **Use boto3 waiters** instead of manual polling where possible. They implement proper backoff (15-second intervals, 40 max attempts by default).

3. **Add explicit wait time** between dependent operations even if Describe calls succeed.

**Warning signs:**
- `InvalidInstanceID.NotFound` errors in logs right after successful `RunInstances`
- `InvalidGroup.NotFound` after `CreateSecurityGroup`
- Flaky tests that pass on retry
- Instance count discrepancies (you launched 5, only 4 appear immediately)

**Phase to address:** Phase 1 (Core EC2 Integration) — This must be built into the initial EC2 client wrapper/wait logic.

---

### Pitfall 2: Underestimating AWS Rate Limiting

**What goes wrong:**
Applications making burst API calls hit `RequestLimitExceeded` or `ThrottlingException` errors. This is especially problematic when:
- Polling instance status too frequently during provisioning
- Bulk operations (starting/stopping many GPU workers at once)
- Health checks that query EC2 API on every check

**Why it happens:**
AWS throttles EC2 API requests per account per region. The exact limits aren't published but are designed to prevent abuse. Standard retry modes default to 3 attempts, which is often insufficient for high-concurrency scenarios.

**Consequences:**
- Worker provisioning fails under load
- Autoscaling becomes unreliable during demand spikes
- Health checks falsely report workers as unhealthy when API calls fail
- Operations timeout unpredictably

**Prevention:**
1. **Configure proper retry settings in boto3**:
   ```python
   from botocore.config import Config
   
   config = Config(
       retries={
           'max_attempts': 10,  # Increase from default 3
           'mode': 'standard'   # Use standard (not legacy) retry mode
       }
   )
   ec2 = boto3.client('ec2', config=config)
   ```

2. **Use adaptive retry mode only with caution**:
   - NOT recommended for multi-tenant applications (like GPUStack serving multiple users)
   - Can delay initial requests, adding latency
   - Only appropriate if you isolate clients per resource

3. **Implement client-side rate limiting**:
   - Add delays between bulk operations
   - Use jitter to prevent thundering herd
   - Cache Describe results briefly instead of querying on every operation

4. **Use EventBridge/SQS for state changes** instead of polling where possible:
   - Subscribe to `EC2 Instance State-change Notification` events
   - React to events rather than polling DescribeInstances

**Warning signs:**
- `RequestLimitExceeded` errors in CloudWatch/Logs
- Operations failing only under load (many concurrent workers)
- Successful retry after transient failures

**Phase to address:** Phase 1 (Core EC2 Integration) — Must be in the EC2 client configuration from day one.

---

### Pitfall 3: Inadequate IAM Permission Scoping

**What goes wrong:**
IAM policies that are either too permissive (security risk) or too restrictive (causing `UnauthorizedOperation` errors). Common mistakes:
- Missing `ec2:CreateVolume` when launching EBS-backed instances
- Forgetting permissions for key pairs, security groups, or subnets
- Not accounting for `ec2:Describe*` permissions required for nearly all operations

**Why it happens:**
AWS EC2 actions require specific permissions for every resource involved in an operation. For example, `RunInstances` needs permissions for:
- The AMI (`ec2:RunInstances` on the AMI resource)
- The instance itself
- The subnet
- The security group
- The key pair
- The volume (if EBS-backed)

**Consequences:**
- "Works on my machine" with admin credentials, fails in production with restricted role
- Users can't launch GPU workers despite having "EC2 access"
- Need to add permissions reactively as failures occur
- Over-permissioned roles create security vulnerabilities

**Prevention:**
1. **Use the IAM policy simulator** to test policies before deployment.

2. **Document minimum required permissions** for GPUStack's AWS integration:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "ec2:RunInstances",
                   "ec2:TerminateInstances",
                   "ec2:DescribeInstances",
                   "ec2:DescribeInstanceStatus",
                   "ec2:DescribeImages",
                   "ec2:DescribeKeyPairs",
                   "ec2:DescribeSecurityGroups",
                   "ec2:DescribeSubnets",
                   "ec2:DescribeVpcs",
                   "ec2:CreateKeyPair",
                   "ec2:DeleteKeyPair",
                   "ec2:CreateTags",
                   "ec2:DescribeVolumes",
                   "ec2:AttachVolume",
                   "ec2:DetachVolume",
                   "ec2:CreateVolume",
                   "ec2:DeleteVolume"
               ],
               "Resource": "*",
               "Condition": {
                   "StringEquals": {
                       "ec2:Region": "us-west-2"
                   }
               }
           }
       ]
   }
   ```

3. **Test with actual restricted role** in development, not admin credentials.

4. **Monitor CloudTrail** for `Client.UnauthorizedOperation` errors.

**Warning signs:**
- `Client.UnauthorizedOperation` errors in logs
- Operations work in dev but fail in production
- Error messages listing specific missing permissions

**Phase to address:** Phase 1 (Core EC2 Integration) — Document and test IAM requirements before any EC2 operations are implemented.

---

### Pitfall 4: Improper Async SDK Patterns

**What goes wrong:**
When using async AWS SDK (aioboto3), blocking the event loop by:
- Calling synchronous boto3 methods in async code
- Not awaiting resource creation properly
- Creating boto3 clients in the wrong scope (creating a new client per request)

**Why it happens:**
Async AWS SDK usage differs from synchronous boto3:
- Service resources must be created with `await`
- All client methods must be awaited
- Client initialization is expensive and should be reused

**Consequences:**
- Event loop blocking causes performance degradation
- Timeouts under concurrent load
- Resource leaks from creating too many clients
- "RuntimeWarning: coroutine was never awaited" errors

**Prevention:**
1. **Initialize clients once and reuse**:
   ```python
   import aioboto3
   
   session = aioboto3.Session()
   
   # Create client once at startup
   ec2 = await session.client('ec2', region_name='us-west-2').__aenter__()
   
   # Reuse for all operations
   async def get_instance_status(instance_id):
       return await ec2.describe_instances(InstanceIds=[instance_id])
   ```

2. **Use proper async context managers**:
   ```python
   async with session.client('ec2') as ec2:
       response = await ec2.run_instances(...)
   ```

3. **Configure AioConfig for retries** (different from synchronous Config):
   ```python
   from aiobotocore.config import AioConfig
   
   config = AioConfig(
       retries={'max_attempts': 10, 'mode': 'standard'}
   )
   ec2 = session.client('ec2', config=config)
   ```

**Warning signs:**
- "RuntimeWarning: coroutine was never awaited"
- Poor performance under concurrent load despite async code
- Connection pool exhaustion errors

**Phase to address:** Phase 1 (Core EC2 Integration) — Async client setup must be architected correctly from the start.

---

### Pitfall 5: Wrong GPU Instance Type / AMI Combinations

**What goes wrong:**
Launching GPU instances (G4dn, P3, P4, P5) with incompatible AMIs or missing GPU drivers. For example:
- Using an AMI without NVIDIA drivers for G4dn instances
- Using a Deep Learning AMI that doesn't support the chosen instance type
- Missing NVIDIA Container Toolkit for Docker-based GPU workloads

**Why it happens:**
AWS Deep Learning AMIs have different driver support:
- **Proprietary Nvidia driver DLAMI**: Supports P3, P3dn, P4, P4de, P5, P5e, P5en
- **OSS Nvidia driver DLAMI**: Supports G4dn, G5, G6, Gr6, G6e, P4, P5, P5e, P5en
- G4dn was removed from proprietary driver support in March 2024

**Consequences:**
- Instances launch but GPU workloads fail with "CUDA not available"
- Driver installation required post-launch, slowing worker startup
- Confusion about why workers show as "running" but can't run GPU jobs

**Prevention:**
1. **Maintain a compatibility matrix** for GPU instance types and AMIs:
   | Instance Type | Required AMI Type | Minimum CUDA |
   |---------------|-------------------|--------------|
   | g4dn.xlarge   | DLAMI OSS GPU     | 12.x         |
   | p3.2xlarge    | DLAMI Proprietary | 11.x+        |
   | p4d.24xlarge  | DLAMI OSS GPU     | 12.x         |

2. **Validate AMI compatibility before launch** using `describe_images` to check the platform details.

3. **Use AWS-provided Deep Learning AMIs** rather than custom AMIs unless necessary.

4. **Test GPU accessibility** as part of worker health checks:
   ```python
   # Verify nvidia-smi works before marking worker ready
   ssh_client.run('nvidia-smi')
   ```

**Warning signs:**
- "CUDA available: False" in logs despite GPU instance
- "NVIDIA kernel module not found" errors
- Instances in "running" state but GPU jobs fail immediately

**Phase to address:** Phase 1 (Core EC2 Integration) — Must be validated at worker creation time.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| **Polling every 5 seconds** instead of using waiters | Faster detection of state changes | Hits rate limits quickly; wastes API quota | Never — use 15-second intervals or EventBridge |
| **Creating new boto3 client per request** | Simpler code, no context manager needed | Connection pool exhaustion; poor performance | Never — reuse clients across requests |
| **Hardcoding AMI IDs** | Quick to implement | AMIs change, become deprecated; breaks in different regions | Only for development; use AMI lookup by name in production |
| **Using a single SSH key for all workers** | Easier key management | Security risk; compromised key affects all workers | Never — generate unique key pairs per worker or use Instance Connect |
| **Ignoring IAM policy boundaries** | Works with admin credentials | Security audit failures; least privilege violations | Never in production |

---

## Integration Gotchas

Common mistakes when connecting to AWS services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **EBS Volume Attachment** | Attempting to attach immediately after volume creation | Wait for volume state = "available" using waiter |
| **EBS Volume Attachment** | Using wrong device name (/dev/sda1 when root already exists) | Use /dev/sdf through /dev/sdp for additional volumes |
| **EBS Volume Attachment** | Attaching to instance in different AZ | Verify volume and instance are in same AZ before attach |
| **SSH Key Pair** | Storing private keys in plaintext | Store in AWS Secrets Manager or Parameter Store, encrypted |
| **SSH Key Pair** | Not cleaning up keys when terminating instances | Implement key lifecycle management; delete keys with instances |
| **Security Groups** | Opening all ports (0.0.0.0/0) for SSH | Restrict to specific IPs or use Session Manager instead |
| **Instance Termination** | Assuming terminate = immediate deletion | Instances can remain in "shutting-down" for minutes; handle gracefully |
| **AZ Selection** | Hardcoding AZ names | AZ names vary by account (us-west-2a != us-west-2a in another account); use AZ IDs |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Polling DescribeInstances every 5s for all workers** | `RequestLimitExceeded` errors; high CloudWatch API metrics costs | Use EventBridge for state change events; poll only when necessary | 20+ workers with 5s polling = ~240 req/min, hitting limits |
| **Synchronous boto3 in async worker pool** | Event loop blocking; requests timing out | Use aioboto3 for true async operations | >10 concurrent worker operations |
| **Creating new EC2 client per API call** | Connection pool exhaustion; slow response times | Initialize one client per region at startup; reuse | >100 requests/minute |
| **No caching of Describe results** | Redundant API calls for same data | Cache instance metadata for 30-60 seconds | Any scale beyond single user |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Storing AWS credentials in worker user data** | Credentials exposed in instance metadata; anyone with EC2 access can retrieve | Use IAM instance profiles instead of hardcoded credentials |
| **Over-permissioned instance profile** | Compromised worker has excessive AWS permissions | Limit instance profile to read-only access to GPUStack-specific resources |
| **SSH key pair without rotation policy** | Long-lived keys increase exposure risk | Generate unique keys per worker; delete on termination |
| **Security group allowing 0.0.0.0/0 on GPU ports** | GPU resources exposed to internet | Restrict to GPUStack server IP or use VPC peering |
| **Not validating AMI ownership** | Accidentally using malicious community AMI | Only use AMIs from "amazon" owner or verified publishers |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **EC2 Instance Launch:** Often missing proper eventual consistency handling — verify wait logic with exponential backoff
- [ ] **Volume Attachment:** Often missing state validation — verify volume is "available" before attach attempt
- [ ] **Worker Health Checks:** Often just check SSH connectivity — verify GPU is accessible (`nvidia-smi` works)
- [ ] **Instance Termination:** Often assumes immediate termination — handle "shutting-down" state properly
- [ ] **IAM Policies:** Often only tested with admin credentials — verify with least-privilege role
- [ ] **SSH Key Cleanup:** Often leave orphaned key pairs — implement key deletion on worker termination
- [ ] **Region Handling:** Often hardcode AZ names — verify AZ ID usage for cross-account consistency
- [ ] **Error Handling:** Often catch generic Exception — handle specific AWS error codes (`InvalidInstanceID.NotFound`, `RequestLimitExceeded`, etc.)

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Eventual consistency race condition | LOW | Implement exponential backoff retry; no data loss |
| Rate limiting burst | LOW | Back off and retry with jitter; consider temporarily reducing polling frequency |
| Wrong AMI for GPU instance | MEDIUM | Terminate instance, launch with correct AMI; any worker state must be rebuilt |
| Orphaned SSH key pairs | LOW | Scan for unused keys by launch time; delete keys older than retention period |
| IAM permission missing | LOW | Add permission to policy; retry operation |
| Volume stuck in "attaching" | MEDIUM | Force detach volume; may require instance stop/start; check for data consistency |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Eventual Consistency | Phase 1: Core EC2 Integration | Unit tests verify wait logic with mocked time delays |
| Rate Limiting | Phase 1: Core EC2 Integration | Load test with 20+ concurrent worker operations |
| IAM Permissions | Phase 1: Core EC2 Integration | CI tests run with restricted IAM role, not admin |
| Async SDK Patterns | Phase 1: Core EC2 Integration | Code review checks for proper client reuse and awaiting |
| GPU AMI Selection | Phase 1: Core EC2 Integration | Integration test launches each supported instance type, verifies GPU access |
| EBS Volume Attachment | Phase 2: Storage Integration | Tests verify volume state checks before attach |
| SSH Key Management | Phase 1: Core EC2 Integration | Security audit confirms key lifecycle (create -> use -> delete) |
| Security Group Config | Phase 1: Core EC2 Integration | Verify no 0.0.0.0/0 rules except where explicitly required |

---

## Sources

- [AWS EC2 Eventual Consistency Documentation](https://docs.aws.amazon.com/ec2/latest/devguide/eventual-consistency.html) — Official AWS documentation on eventual consistency model
- [AWS SDK Retry Behavior](https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html) — Official retry mode and throttling documentation
- [AWS EC2 API Troubleshooting](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/query-api-troubleshooting.html) — Official API error guidance
- [AWS DLAMI Release Notes](https://docs.aws.amazon.com/dlami/latest/devguide/aws-deep-learning-base-gpu-ami-ubuntu-20.04.html) — GPU instance type support matrix
- [EBS Volume Attachment Issues](https://repost.aws/knowledge-center/ebs-resolve-attach-volume-instance-issue) — Common EBS attachment errors and solutions
- [AWS IAM Troubleshooting](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_iam-ec2.html) — IAM permission error patterns
- [Moto EC2 Testing](https://docs.getmoto.org/en/latest/docs/services/ec2.html) — EC2 mocking for unit tests
- [aioboto3 Usage](https://aioboto3.readthedocs.io/en/latest/usage.html) — Async SDK patterns
- [GPUStack DigitalOcean Integration](https://docs.gpustack.ai/2.0/tutorials/adding-gpucluster-using-digitalocean/) — Reference for existing cloud integration patterns

---

*Pitfalls research for: AWS EC2 GPU Worker Integration*
*Researched: 2026-01-31*
