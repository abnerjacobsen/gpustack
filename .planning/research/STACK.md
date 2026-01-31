# Technology Stack: AWS EC2 Integration for GPUStack

**Domain:** AWS Cloud Provider Integration for GPU Cluster Management  
**Researched:** 2026-01-31  
**Confidence:** HIGH

## Executive Summary

For GPUStack's AWS EC2 GPU worker support, **aiobotocore 3.1.1** is the definitive choice. It provides native async AWS SDK access with full EC2, EBS, and IAM (SSH key) API coverage. The library is actively maintained (latest release Jan 20, 2026), part of the well-established aio-libs ecosystem, and directly mirrors the official boto3 API structure—making it the optimal drop-in async replacement for synchronous boto3 code.

**Key Decision:** Use `aiobotocore` directly (not `aioboto3`) because GPUStack's cloud provider abstraction only needs low-level client operations (instance lifecycle, volume management, SSH key CRUD) rather than high-level boto3 resource abstractions.

---

## Recommended Stack

### Core Technology

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **aiobotocore** | ^3.1.1 | Async AWS SDK client for EC2, EBS, IAM operations | Official async implementation of botocore; direct 1:1 API parity with boto3; actively maintained by aio-libs organization; battle-tested in production with 1.4k GitHub stars |
| **botocore** | ^1.36.0 (transitive) | Core AWS service definitions and request handling | Automatically managed by aiobotocore; provides the service model definitions for all AWS APIs |
| **aiohttp** | ^3.10.0 (transitive) | HTTP client for AWS API requests | Automatically managed by aiobotocore; handles async HTTP connections, pooling, and retries |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **types-aiobotocore[essential]** | ^2.15.0 | Type stubs for aiobotocore | Enable mypy/pylance type checking and IDE autocomplete for EC2/EBS/IAM clients |
| **types-aiobotocore[ec2,ebs,iam]** | ^2.15.0 | Service-specific type stubs | Install if you need precise typing for only specific services (lighter weight) |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **moto** | AWS service mocking for tests | Use `moto[ec2]` for EC2/EBS mocking in unit tests |
| **pytest-asyncio** | Async test runner | Required for testing async aiobotocore code; use `pytest-asyncio>=0.23.0` for AnyIO compatibility |

---

## Installation

```bash
# Core dependency
pip install aiobotocore>=3.1.1

# Development dependencies (optional but recommended)
pip install types-aiobotocore[essential]  # For IDE autocomplete and type checking
pip install moto[ec2]                     # For mocking AWS in tests
```

### Pyproject.toml entry:

```toml
[project.dependencies]
aiobotocore = "^3.1.1"

[project.optional-dependencies]
dev = [
    "types-aiobotocore[essential]>=2.15.0",
    "moto[ec2]>=5.0.0",
]
```

---

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| **AWS SDK** | aiobotocore 3.1.1 | aioboto3 15.5.0 | Use aioboto3 only if you need high-level boto3 resource abstractions (e.g., `resource('dynamodb').Table()` patterns) |
| **AWS SDK** | aiobotocore 3.1.1 | boto3 + asyncio.to_thread | Use only if you cannot migrate to aiobotocore; wrapping sync boto3 in threads loses connection pooling and adds overhead |
| **AWS SDK** | aiobotocore 3.1.1 | awslabs/aws-sdk-python (experimental) | Avoid—this is AWS's experimental next-gen SDK, still in early development as of 2025, not production-ready |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **aiobotocore < 3.0.0** | Version 3.0.0 introduced breaking changes requiring async context managers (`async with client:`). Pre-3.x versions are deprecated and may have connection leak issues | aiobotocore ^3.1.1 |
| **aioboto3 for EC2-only operations** | aioboto3 adds unnecessary abstraction layer and dependency overhead when you only need low-level EC2/EBS client operations | aiobotocore directly |
| **Synchronous boto3 in async code** | Blocking I/O calls will stall the entire event loop, destroying throughput for a cluster manager | aiobotocore or executor pools |
| **ThreadPoolExecutor wrapping boto3** | While functional, it wastes threads, loses connection reuse, and complicates error handling | Native aiobotocore |

---

## Architecture Fit for GPUStack

### Why aiobotocore Matches GPUStack's Pattern

GPUStack's existing `DigitalOceanClient` uses `pydo.aio.Client` with this pattern:

```python
# DigitalOcean pattern (existing)
from pydo.aio import Client
self.client = Client(token=token, timeout=30)
droplet_resp = await self.client.droplets.create(body=req)
```

aiobotocore provides the exact same low-level client pattern:

```python
# AWS pattern (recommended)
from aiobotocore.session import get_session

session = get_session()
async with session.create_client('ec2', region_name='us-east-1', 
                                  aws_access_key_id=ak, 
                                  aws_secret_access_key=sk) as client:
    resp = await client.run_instances(...)
```

### Implementation Mapping

| DigitalOceanClient Method | aiobotocore EC2 Equivalent |
|---------------------------|---------------------------|
| `create_instance()` | `client.run_instances()` |
| `delete_instance()` | `client.terminate_instances()` |
| `get_instance()` | `client.describe_instances()` |
| `create_ssh_key()` | `client.import_key_pair()` |
| `delete_ssh_key()` | `client.delete_key_pair()` |
| `create_volumes_and_attach()` | `client.create_volume()` + `client.attach_volume()` |

---

## Critical API Changes (aiobotocore 3.x)

**BREAKING CHANGE:** aiobotocore 3.0.0+ requires async context managers. The client MUST be used with `async with`:

```python
# CORRECT (aiobotocore 3.x)
async with session.create_client('ec2') as client:
    resp = await client.describe_instances()

# INCORRECT (will fail or leak connections)
client = session.create_client('ec2')  # Don't do this
resp = await client.describe_instances()
```

**Migration from pre-3.x:** If any existing code uses aiobotocore, it must be updated to use context managers. See [aiobotocore 3.0.0 release notes](https://github.com/aio-libs/aiobotocore/releases/tag/3.0.0).

---

## Version Compatibility

| Package | Compatible Versions | Notes |
|---------|---------------------|-------|
| aiobotocore 3.1.1 | botocore ^1.36.0 | Automatically managed by aiobotocore's dependency specification |
| aiobotocore 3.1.1 | Python 3.9 - 3.14 | Requires Python 3.9+ (dropped 3.8 support in 2.23.0) |
| aiobotocore 3.1.1 | aiohttp ^3.9.0 | Uses aiohttp for HTTP transport |

---

## Implementation Example

```python
from aiobotocore.session import get_session
from botocore.config import Config

class AWSClient:
    def __init__(self, access_key: str, secret_key: str, region: str):
        self.session = get_session()
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        # Optional: configure retries/timeout
        self.config = Config(
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            connect_timeout=10,
            read_timeout=30,
        )
    
    async def __aenter__(self):
        self.client = await self.session.create_client(
            'ec2',
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=self.config
        ).__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def create_instance(self, name: str, instance_type: str, image_id: str):
        resp = await self.client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': name}]
            }]
        )
        return resp['Instances'][0]['InstanceId']

# Usage
async with AWSClient(ak, sk, 'us-east-1') as aws:
    instance_id = await aws.create_instance('worker-1', 'p3.2xlarge', 'ami-12345')
```

---

## GPU Instance Considerations

For GPUStack's use case (p3, p4d, g4dn, g5 families):

| Instance Family | API Considerations |
|-----------------|-------------------|
| **p3, p4d** | Require VPC and subnet specification; p4d may need Elastic Fabric Adapter (EFA) settings |
| **g4dn, g5** | Standard EC2 launch; ensure AMI has NVIDIA drivers or use user-data to install GPU drivers |
| **All GPU** | Consider `InstanceMarketOptions` for Spot instances to reduce costs |

---

## Sources

1. **aiobotocore PyPI** (Jan 20, 2026) — https://pypi.org/project/aiobotocore/3.1.1/ — Version confirmation, dependencies
2. **aiobotocore Documentation** — https://aiobotocore.aio-libs.org/ — Official docs, examples, API patterns
3. **aiobotocore GitHub** — https://github.com/aio-libs/aiobotocore — Release notes, 3.0.0 breaking changes
4. **aioboto3 PyPI** (Oct 30, 2025) — https://pypi.org/project/aioboto3/15.5.0/ — Alternative analysis
5. **AWS boto3 EC2 Docs** — https://boto3.amazonaws.com/v1/documentation/api/latest/guide/ec2-example-managing-instances.html — API method mapping
6. **Medium: aiobotocore 2.25.0 and AnyIO** (Oct 2025) — https://medium.com/h7w/pythons-async-aiobotocore-2-25-0 — Background on AnyIO migration

---

*Stack research for: AWS EC2 GPU Worker Integration*  
*Researched: 2026-01-31*  
*Confidence: HIGH*
