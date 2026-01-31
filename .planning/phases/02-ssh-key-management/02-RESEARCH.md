# Phase 02: SSH Key Management - Research

**Researched:** 2026-01-31
**Domain:** AWS EC2 SSH Key Pairs (import_key_pair/delete_key_pair APIs)
**Confidence:** HIGH

## Summary

This phase implements the `create_ssh_key()` and `delete_ssh_key()` methods for the AWS EC2 provider in GPUStack. The research confirms that AWS supports both RSA and ED25519 SSH keys, with ED25519 being the modern recommendation for Linux instances. The existing GPUStack codebase already contains SSH key generation infrastructure using the Python `cryptography` library.

**Primary Recommendation:**
- **Key Type:** ED25519 for new keys (faster, more secure, modern standard)
- **Library:** Python `cryptography` (already in dependencies)
- **Key Format:** OpenSSH format (required by AWS import_key_pair API)
- **Naming:** `gpustack-{worker-name}-{random-suffix}` with 8-char alphanumeric suffix
- **Private Key Storage:** Base64-encoded, encrypted in database using GPUStack's existing credential security

**Key findings:**
1. AWS EC2 officially supports ED25519 keys for Linux instances (since Aug 2021)
2. ED25519 keys are NOT supported for Windows instances (must use RSA)
3. AWS import_key_pair requires OpenSSH public key format
4. Fingerprint formats differ: MD5 for RSA, SHA-256 base64 for ED25519
5. GPUStack already has `generate_ssh_key_pair()` in `cloud_providers/common.py`
6. The `Credential` schema already supports SSH key storage

## Standard Stack

### Core Libraries
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cryptography | >=43.0.0 | SSH key generation | Already in GPUStack deps, industry standard |
| aiobotocore | >=3.1.1 | AWS EC2 API calls | Already chosen for AWS client (Phase 1) |
| moto[ec2] | >=5.0.0 | Testing/mocking AWS | Already in deps for testing |

### No Additional Dependencies Required
The existing GPUStack infrastructure is sufficient:
- `cryptography` library handles ED25519/RSA key generation
- `aiobotocore` provides async EC2 client
- SQLModel/SQLAlchemy handles database storage

## Architecture Patterns

### Recommended Project Structure
```
gpustack/cloud_providers/
├── abstract.py          # ProviderClientBase interface (exists)
├── aws.py               # AWSClient implementation (exists, needs methods)
├── common.py            # Shared utilities including generate_ssh_key_pair (exists)
├── digital_ocean.py     # Reference implementation (exists)
└── user_data.py         # Cloud-init templates (exists)

Key integration points:
- server/controllers.py  # _create_ssh_key() already calls client.create_ssh_key()
- schemas/clusters.py    # CloudCredential schema (exists)
- schemas/workers.py     # Worker model with ssh_key_id (exists)
```

### Pattern 1: Follow DigitalOcean Implementation
**What:** Use DigitalOcean's `create_ssh_key` as reference for AWS implementation
**When to use:** AWS implementation should follow same pattern
**Example:**
```python
# From digital_ocean.py - reference pattern
async def create_ssh_key(self, worker_name: str, public_key: str) -> str:
    ssh_key_resp = await self.client.ssh_keys.create(
        body={"name": f"sshkey-{worker_name}", "public_key": public_key},
    )
    id = ssh_key_resp['ssh_key']['id']
    return str(id)

async def delete_ssh_key(self, id: str):
    await self.client.ssh_keys.delete(id)
```

### Pattern 2: AWS EC2 Key Pair API Pattern
**What:** Use aiobotocore EC2 client for import_key_pair and delete_key_pair
**When to use:** AWS provider implementation
**Example:**
```python
# AWS-specific implementation pattern
async def create_ssh_key(self, worker_name: str, public_key: str) -> str:
    """Import SSH public key to AWS EC2.
    
    Args:
        worker_name: Name of the worker (used in key naming)
        public_key: SSH public key in OpenSSH format
        
    Returns:
        AWS key pair name (not ID - AWS uses name as identifier for import)
    """
    key_name = f"gpustack-{worker_name}-{generate_suffix()}"
    
    async with self._get_client() as client:
        # Check if key already exists first
        try:
            await client.describe_key_pairs(KeyNames=[key_name])
            raise RuntimeError(f"Key pair '{key_name}' already exists in AWS")
        except ClientError as e:
            if e.response['Error']['Code'] != 'InvalidKeyPair.NotFound':
                raise
        
        # Import the public key
        response = await client.import_key_pair(
            KeyName=key_name,
            PublicKeyMaterial=public_key.encode('utf-8'),
            TagSpecifications=[{
                'ResourceType': 'key-pair',
                'Tags': [
                    {'Key': 'ManagedBy', 'Value': 'GPUStack'},
                    {'Key': 'WorkerName', 'Value': worker_name}
                ]
            }]
        )
        return response['KeyName']  # AWS returns the name we provided

async def delete_ssh_key(self, id: str) -> None:
    """Delete AWS EC2 key pair by name.
    
    Args:
        id: AWS key pair name (the 'name' we used, not a numeric ID)
    """
    async with self._get_client() as client:
        await client.delete_key_pair(KeyName=id)
```

### Pattern 3: Check Before Create
**What:** Always check if key exists before attempting creation
**When to use:** To avoid InvalidKeyPair.Duplicate errors
**Example:**
```python
async def _check_key_exists(self, client, key_name: str) -> bool:
    try:
        await client.describe_key_pairs(KeyNames=[key_name])
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidKeyPair.NotFound':
            return False
        raise
```

### Anti-Patterns to Avoid
- **Don't rely on error handling for existence checks:** Check proactively with `describe_key_pairs`
- **Don't use AWS create_key_pair:** It generates keys on AWS side, but GPUStack generates keys locally
- **Don't return private key in responses:** Store encrypted, never expose
- **Don't use short key names:** Include random suffix to prevent collisions

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSH key generation | Custom crypto code | `cryptography` library | Security, auditability, maintained |
| Key format conversion | Manual string manipulation | `cryptography.hazmat.primitives.serialization` | Correct OpenSSH format required by AWS |
| Fingerprint calculation | MD5/SHA256 hashing | Use AWS-returned fingerprint | AWS calculates differently for ED25519 vs RSA |
| AWS API mocking | Custom mocks | `moto[ec2]` | Already in deps, comprehensive |
| Private key storage | Plaintext or custom encryption | GPUStack's existing credential encryption | Consistent security model |

**Key insight:** AWS key pair fingerprints are calculated differently for different key types:
- RSA: MD5 fingerprint per RFC 4716 section 4
- ED25519: Base64-encoded SHA-256 digest (OpenSSH 6.8+ format)

Trust the fingerprint returned by AWS's `import_key_pair` response rather than calculating locally.

## Common Pitfalls

### Pitfall 1: ED25519 Key Format Mismatch
**What goes wrong:** AWS `import_key_pair` rejects ED25519 keys if not in exact OpenSSH format
**Why it happens:** Different tools generate slightly different formats
**How to avoid:** Use `cryptography` library with `serialization.Encoding.OpenSSH` and `serialization.PublicFormat.OpenSSH`
**Warning signs:** `InvalidKey.Format` error from AWS

### Pitfall 2: Windows Instance Incompatibility
**What goes wrong:** ED25519 keys work for Linux instances but fail for Windows
**Why it happens:** AWS doesn't support ED25519 for Windows (as of 2026)
**How to avoid:** Document limitation, consider using RSA 2048 for mixed environments
**Warning signs:** Connection failures to Windows instances

### Pitfall 3: Key Name Collisions
**What goes wrong:** Duplicate key names cause `InvalidKeyPair.Duplicate` errors
**Why it happens:** AWS key pair names are per-region, must be unique
**How to avoid:** Always check with `describe_key_pairs` before import, use random suffix
**Warning signs:** Intermittent failures with "already exists" errors

### Pitfall 4: Fingerprint Mismatch in Verification
**What goes wrong:** Local fingerprint calculation differs from AWS's calculation
**Why it happens:** ED25519 uses SHA-256, RSA uses MD5; different encoding
**How to avoid:** Use fingerprint from `import_key_pair` response, don't recalculate
**Warning signs:** Fingerprint verification fails after successful import

### Pitfall 5: Private Key Storage Format
**What goes wrong:** Private key can't be reconstructed for usage
**Why it happens:** ED25519 raw bytes need proper encoding for storage
**How to avoid:** Store base64-encoded raw bytes (GPUStack pattern), reconstruct with `Ed25519PrivateKey.from_private_bytes()`
**Warning signs:** Can't reconstruct private key from stored data

## Code Examples

### Generate ED25519 SSH Key Pair
```python
# Source: gpustack/cloud_providers/common.py (existing code)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import base64

def generate_ssh_key_pair(algorithm: str = "ED25519") -> Tuple[str, str]:
    """
    Generate SSH key pair.
    Returns: (private_key_base64, public_key_openssh)
    """
    if algorithm.upper() == "ED25519":
        key = ed25519.Ed25519PrivateKey.generate()
        # Store raw bytes (base64 encoded for storage)
        key_bytes = key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Generate OpenSSH format public key
        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode()
    else:  # RSA
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_bytes = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode()
    
    private_key_b64 = base64.b64encode(key_bytes).decode()
    return private_key_b64, public_key
```

### Reconstruct Private Key from Storage
```python
# Source: gpustack/cloud_providers/common.py (existing code)
def key_bytes_to_openssh_pem(key_bytes: bytes, algorithm: str) -> bytes:
    """Convert stored key bytes back to OpenSSH PEM format."""
    if algorithm.upper() == "RSA":
        return key_bytes  # Already in PEM format
    elif algorithm.upper() == "ED25519":
        key = ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        )
    else:
        raise ValueError("Unsupported algorithm")
```

### AWS Import Key Pair with Error Handling
```python
# Source: Based on AWS documentation and patterns
from botocore.exceptions import ClientError

async def create_ssh_key(self, worker_name: str, public_key: str) -> str:
    """Import SSH public key to AWS EC2.
    
    Returns:
        Key pair name (used as identifier in AWS)
    """
    import secrets
    suffix = secrets.token_hex(4)  # 8 characters
    key_name = f"gpustack-{worker_name}-{suffix}"
    
    async with self._get_client() as client:
        # Check for existing key
        try:
            await client.describe_key_pairs(KeyNames=[key_name])
            raise RuntimeError(
                f"Key pair '{key_name}' already exists in AWS. "
                f"Fingerprint: {existing_fingerprint}. "
                "Please delete the existing key or use a different worker name."
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'InvalidKeyPair.NotFound':
                raise self._handle_aws_error(e, "SSH key existence check")
        
        # Import the key
        try:
            response = await client.import_key_pair(
                KeyName=key_name,
                PublicKeyMaterial=public_key.encode('utf-8'),
                TagSpecifications=[{
                    'ResourceType': 'key-pair',
                    'Tags': [
                        {'Key': 'ManagedBy', 'Value': 'GPUStack'},
                        {'Key': 'WorkerName', 'Value': worker_name}
                    ]
                }]
            )
            
            logger.info(
                f"Imported SSH key '{key_name}' to AWS. "
                f"Fingerprint: {response.get('KeyFingerprint')}"
            )
            return response['KeyName']
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidKey.Format':
                raise RuntimeError(
                    "Invalid SSH public key format. "
                    "AWS requires OpenSSH format (ssh-ed25519 AAAAC3... or ssh-rsa AAAAB3...)"
                ) from e
            elif error_code == 'InvalidKeyPair.Duplicate':
                raise RuntimeError(
                    f"Key pair '{key_name}' already exists in AWS"
                ) from e
            raise self._handle_aws_error(e, "SSH key import")
```

### AWS Delete Key Pair
```python
async def delete_ssh_key(self, id: str) -> None:
    """Delete EC2 key pair by name.
    
    Args:
        id: Key pair name (the identifier returned by create_ssh_key)
    """
    async with self._get_client() as client:
        try:
            await client.delete_key_pair(KeyName=id)
            logger.info(f"Deleted SSH key pair '{id}' from AWS")
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidKeyPair.NotFound':
                logger.warning(f"Key pair '{id}' not found in AWS (already deleted)")
                return
            raise self._handle_aws_error(e, "SSH key deletion")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RSA 1024/2048 | ED25519 or RSA 4096 | 2021 (AWS added ED25519) | ED25519 is faster, more secure, smaller keys |
| AWS create_key_pair | Local generation + import | GPUStack design decision | Better security - private key never leaves GPUStack |
| MD5 fingerprints | SHA-256 for ED25519 | OpenSSH 6.8+ | Different fingerprint format requires handling |
| PEM private keys | OpenSSH format | Modern OpenSSH | Better compatibility, can include comments |

**Deprecated/outdated:**
- DSA keys: AWS never supported them
- RSA 1024: Considered too weak, use 2048+ or ED25519
- SSH2 format (RFC 4716): Use OpenSSH format for import

## Open Questions

1. **Private key usage pattern**
   - What we know: Private keys are stored in database, never returned to users
   - What's unclear: Does GPUStack server need to SSH to workers, or is it just for worker bootstrap?
   - Recommendation: Keep infrastructure ready for both; design for potential future SSH access needs

2. **Deletion policy for private keys**
   - What we know: Key pairs should be deleted when workers are deleted
   - What's unclear: Should private keys be retained (soft delete) for audit/compliance?
   - Recommendation: Document policy clearly; consider compliance requirements

3. **Multi-region key behavior**
   - What we know: AWS key pairs are per-region
   - What's unclear: Should key names include region to avoid cross-region collisions?
   - Recommendation: Key name pattern `gpustack-{worker-name}-{suffix}` should be sufficient since worker names should be unique across regions

4. **Windows instance support**
   - What we know: ED25519 not supported for Windows
   - What's unclear: Will GPUStack support Windows GPU instances?
   - Recommendation: If Windows support needed later, implement RSA 2048 path

## Sources

### Primary (HIGH confidence)
- GPUStack codebase:
  - `gpustack/cloud_providers/common.py` - existing `generate_ssh_key_pair()` implementation
  - `gpustack/cloud_providers/abstract.py` - ProviderClientBase interface
  - `gpustack/cloud_providers/digital_ocean.py` - reference implementation
  - `gpustack/cloud_providers/aws.py` - AWS client (stubs to be implemented)
  - `gpustack/server/controllers.py` - `_create_ssh_key()` caller
  - `gpustack/schemas/workers.py` - Credential schema with SSH support
- AWS Official Documentation:
  - https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html
  - https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ImportKeyPair.html
  - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2/client/import_key_pair.html

### Secondary (MEDIUM confidence)
- Python cryptography library docs: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- AWS announcement (Aug 2021): ED25519 support added to EC2
- StackOverflow discussions on AWS key pair formats

### Tertiary (LOW confidence)
- Community blog posts on SSH key generation patterns (2024-2025)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing GPUStack infrastructure
- Architecture: HIGH - Clear patterns from DigitalOcean implementation
- Pitfalls: HIGH - AWS docs explicitly specify format requirements

**Research date:** 2026-01-31
**Valid until:** 90 days (AWS APIs are stable, but verify ED25519 support if Windows instances become a requirement)

**Pre-existing code verification:**
- `generate_ssh_key_pair()` exists and uses correct `cryptography` patterns
- ED25519 private key stored as raw bytes (base64 encoded) - correct for reconstruction
- RSA private key stored in OpenSSH PEM format - correct
- Credential schema has `encoded_private_key` field - ready for storage
- `_create_ssh_key()` in controllers.py already calls `client.create_ssh_key()` - interface ready

**Testing approach:**
- Use `moto[ec2]` mock for unit tests (already in dependencies)
- Test both ED25519 and RSA key generation
- Test key name collision handling
- Test error handling for InvalidKey.Format
- Test fingerprint format handling
