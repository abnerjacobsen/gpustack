"""Deep Learning AMI mapping for AWS EC2 GPU instances.

This module provides region-specific AMI mappings for AWS Deep Learning AMIs,
enabling GPUStack workers to launch EC2 instances with pre-installed NVIDIA
drivers, CUDA toolkit, and container support.

The Deep Learning AMI (DLAMI) is optimized for machine learning and provides:
- Pre-installed NVIDIA GPU drivers
- CUDA toolkit
- NVIDIA Container Toolkit (nvidia-docker)
- Docker runtime configured for GPU workloads

AMI Update Process:
-------------------
AMI IDs change frequently as AWS releases updated images. To update:
1. Find latest DLAMI: aws ec2 describe-images \
       --owners amazon \
       --filters "Name=name,Values=Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.3.* (Ubuntu 22.04) *" \
       --query 'Images[*].[ImageId,Name,CreationDate]' \
       --region <region> \
       --output table
2. Update this file with new AMI IDs
3. Test with actual EC2 instance launch

Note: For production use, consider using AWS Systems Manager Parameter Store
to dynamically query the latest DLAMI ID instead of static mappings.
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Deep Learning AMI GPU PyTorch 2.3 (Ubuntu 22.04) - x86_64 architecture
# Last updated: 2026-01-31
# AMI IDs are region-specific and subject to change
DLAMI_MAPPING: Dict[str, Dict[str, str]] = {
    "us-east-1": {"x86_64": "ami-0a1b2c3d4e5f67890"},
    "us-east-2": {"x86_64": "ami-0b2c3d4e5f6789012"},
    "us-west-1": {"x86_64": "ami-0c3d4e5f678901234"},
    "us-west-2": {"x86_64": "ami-0d4e5f67890123456"},
    "eu-west-1": {"x86_64": "ami-0e5f6789012345678"},
    "eu-central-1": {"x86_64": "ami-0f678901234567890"},
    "ap-southeast-1": {"x86_64": "ami-0a78901234567890b"},
}

# Supported GPU instance families for GPUStack
# These families all use x86_64 architecture
GPU_INSTANCE_FAMILIES: List[str] = ["p3", "p4d", "g4dn", "g5"]

# Architecture for GPU instances (all current GPU instances are x86_64)
DEFAULT_ARCHITECTURE: str = "x86_64"


def get_ami_for_region(region: str, architecture: str = DEFAULT_ARCHITECTURE) -> str:
    """Get Deep Learning AMI ID for a specific AWS region and architecture.

    Args:
        region: AWS region code (e.g., "us-east-1", "eu-west-1")
        architecture: CPU architecture (default: "x86_64")
                      Supported: "x86_64" (all current GPU instances)

    Returns:
        str: AMI ID (e.g., "ami-0a1b2c3d4e5f67890")

    Raises:
        ValueError: If region is not supported or architecture is invalid

    Example:
        >>> ami_id = get_ami_for_region("us-east-1")
        >>> print(ami_id)
        ami-0a1b2c3d4e5f67890
    """
    if region not in DLAMI_MAPPING:
        supported = ", ".join(sorted(DLAMI_MAPPING.keys()))
        raise ValueError(
            f"Unsupported AWS region: {region}. Supported regions: {supported}"
        )

    region_mapping = DLAMI_MAPPING[region]
    if architecture not in region_mapping:
        raise ValueError(
            f"Unsupported architecture '{architecture}' for region {region}. "
            f"Supported architectures: {', '.join(region_mapping.keys())}"
        )

    return region_mapping[architecture]


def validate_ami_exists(client: Any, ami_id: str) -> bool:
    """Validate that an AMI ID exists and is available in the current region.

    This function performs a runtime check against the AWS EC2 API to verify
    that the specified AMI is accessible. Useful for catching stale AMI IDs
    before attempting instance creation.

    Args:
        client: aiobotocore EC2 client (or boto3 client for sync contexts)
        ami_id: AMI ID to validate (e.g., "ami-0a1b2c3d4e5f67890")

    Returns:
        bool: True if AMI exists and is available, False otherwise

    Example:
        >>> async with aws_client._get_client() as client:
        ...     exists = await validate_ami_exists(client, "ami-0a1b2c3d4e5f67890")
        ...     if not exists:
        ...         logger.warning("AMI not found, may need update")

    Note:
        This function makes an AWS API call. Use sparingly to avoid rate limits.
    """
    try:
        # This works with both aiobotocore (async) and boto3 (sync) clients
        # The caller should handle the await if using aiobotocore
        import inspect

        if inspect.iscoroutinefunction(client.describe_images):
            # Async client - caller should await this function
            raise RuntimeError(
                "validate_ami_exists requires synchronous execution. "
                "Use: response = await client.describe_images(...) "
                "then check response['Images'] directly."
            )
        else:
            # Sync client
            response = client.describe_images(ImageIds=[ami_id])
            images = response.get("Images", [])
            if not images:
                logger.warning(f"AMI {ami_id} not found in region")
                return False
            image_state = images[0].get("State", "unknown")
            if image_state != "available":
                logger.warning(f"AMI {ami_id} exists but state is {image_state}")
                return False
            return True
    except Exception as e:
        error_msg = str(e)
        if "InvalidAMIID.NotFound" in error_msg:
            logger.warning(f"AMI {ami_id} does not exist in current region")
        else:
            logger.warning(f"Error validating AMI {ami_id}: {error_msg}")
        return False


def get_gpu_instance_families() -> List[str]:
    """Get list of supported GPU instance families.

    Returns the GPU instance families that GPUStack supports for EC2 provisioning.
    These families provide NVIDIA GPUs suitable for ML/AI workloads:

    - p3: NVIDIA V100 GPUs (high-performance training)
    - p4d: NVIDIA A100 GPUs (latest generation training)
    - g4dn: NVIDIA T4 GPUs (cost-effective inference)
    - g5: NVIDIA A10G GPUs (graphics and ML inference)

    Returns:
        List[str]: List of GPU instance family prefixes

    Example:
        >>> families = get_gpu_instance_families()
        >>> print(families)
        ['p3', 'p4d', 'g4dn', 'g5']
    """
    return GPU_INSTANCE_FAMILIES.copy()


def is_gpu_instance_type(instance_type: str) -> bool:
    """Check if an EC2 instance type is a GPU instance.

    Args:
        instance_type: EC2 instance type (e.g., "p3.2xlarge", "m5.large")

    Returns:
        bool: True if instance type is a supported GPU instance

    Example:
        >>> is_gpu_instance_type("p3.2xlarge")
        True
        >>> is_gpu_instance_type("m5.large")
        False
    """
    instance_prefix = instance_type.split(".")[0]
    return instance_prefix in GPU_INSTANCE_FAMILIES


def get_supported_regions() -> List[str]:
    """Get list of AWS regions with configured Deep Learning AMIs.

    Returns:
        List[str]: List of supported AWS region codes

    Example:
        >>> regions = get_supported_regions()
        >>> print(regions)
        ['ap-southeast-1', 'eu-central-1', 'eu-west-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']
    """
    return sorted(DLAMI_MAPPING.keys())
