"""AWS EC2 cloud provider client using aiobotocore.

This module implements the ProviderClientBase interface for AWS EC2,
providing async operations for GPU instance lifecycle management.
"""

import asyncio
import logging
import secrets
from typing import List, Optional, Dict, Any, Tuple

from aiobotocore.session import get_session
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

from .abstract import (
    ProviderClientBase,
    CloudInstance,
    CloudInstanceCreate,
    InstanceState,
)
from gpustack.schemas.clusters import Volume
from gpustack.schemas.aws import AWSConfig

logger = logging.getLogger(__name__)

# AWS EC2 instance state mapping to InstanceState
status_mapping = {
    "pending": InstanceState.CREATED,
    "running": InstanceState.RUNNING,
    "stopping": InstanceState.STOPPING,
    "stopped": InstanceState.STOPPED,
    "terminated": InstanceState.TERMINATED,
    "shutting-down": InstanceState.STOPPING,
}


class AWSClient(ProviderClientBase):
    """AWS EC2 cloud provider client using aiobotocore.

    Implements the ProviderClientBase interface for AWS EC2 GPU instance
    provisioning and management. Uses aiobotocore for async AWS API operations
    with configurable retry policies.

    Attributes:
        access_key: AWS access key ID
        secret_key: AWS secret access key
        region: AWS region (e.g., us-east-1)
        config: Optional AWSConfig with additional settings
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str,
        config: Optional[AWSConfig] = None,
    ):
        """Initialize AWS EC2 client with credentials and configuration.

        Args:
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region code
            config: Optional AWSConfig with VPC/subnet/security group settings
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.config = config

        # Configure retry with max_attempts: 10 as per AWS best practices
        self.boto_config = Config(
            retries={"max_attempts": 10, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=30,
        )
        self._session = get_session()

    async def _get_client(self):
        """Get aiobotocore EC2 client with proper configuration.

        Returns:
            EC2 client context manager for use in async with statements
        """
        return self._session.create_client(
            "ec2",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=self.boto_config,
        )

    def _handle_aws_error(self, error: Exception, operation: str) -> RuntimeError:
        """Convert AWS exceptions to user-friendly error messages.

        Args:
            error: The exception raised by AWS SDK
            operation: Description of the operation being performed

        Returns:
            RuntimeError with user-friendly message wrapping the original error
        """
        if isinstance(error, ClientError):
            error_code = error.response["Error"]["Code"]
            error_msg = error.response["Error"]["Message"]
            logger.error(f"AWS {operation} failed: {error_code} - {error_msg}")
            return RuntimeError(f"AWS {operation} failed: {error_code} - {error_msg}")
        elif isinstance(error, NoCredentialsError):
            logger.error(f"AWS credentials invalid for {operation}")
            return RuntimeError(
                "Invalid AWS credentials. Please check your access key and secret key."
            )
        elif isinstance(error, EndpointConnectionError):
            logger.error(f"AWS connection failed for {operation}: {error}")
            return RuntimeError(
                f"Cannot connect to AWS EC2 in region {self.region}. "
                "Please check your network connection."
            )
        else:
            logger.error(f"Unexpected error during {operation}: {error}")
            return RuntimeError(f"AWS {operation} failed: {str(error)}")

    async def _check_key_exists(
        self, client, key_name: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if EC2 key pair exists in AWS.

        Args:
            client: aiobotocore EC2 client
            key_name: Name of the key pair to check

        Returns:
            Tuple of (exists: bool, fingerprint: Optional[str])
        """
        try:
            response = await client.describe_key_pairs(KeyNames=[key_name])
            key_info = response.get("KeyPairs", [{}])[0]
            fingerprint = key_info.get("KeyFingerprint")
            return True, fingerprint
        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidKeyPair.NotFound":
                return False, None
            raise self._handle_aws_error(e, "SSH key existence check")

    async def validate_credentials(self) -> bool:
        """Validate AWS credentials by calling EC2 describe_regions.

        Uses a lightweight EC2 API call to verify credentials are valid
        and can successfully authenticate to AWS. This is a read-only
        operation that requires minimal IAM permissions.

        Returns:
            True if credentials are valid

        Raises:
            RuntimeError: If credentials are invalid or API call fails
        """
        try:
            async with self._get_client() as client:
                response = await client.describe_regions(RegionNames=[self.region])
                if response.get("Regions"):
                    logger.info(f"AWS credentials validated for region {self.region}")
                    return True
                raise RuntimeError(
                    "AWS credentials validation failed: no regions returned"
                )
        except (ClientError, NoCredentialsError) as e:
            raise self._handle_aws_error(e, "credential validation")
        except Exception as e:
            logger.error(f"Unexpected error during credential validation: {e}")
            raise RuntimeError(f"Failed to validate AWS credentials: {str(e)}") from e

    async def create_instance(self, instance: CloudInstanceCreate) -> Optional[str]:
        """Create an EC2 instance (stub for Phase 2 implementation).

        Args:
            instance: CloudInstanceCreate with instance specifications

        Returns:
            Instance ID as string, or None if creation failed

        Raises:
            NotImplementedError: Full implementation in Phase 2
        """
        raise NotImplementedError(
            "create_instance implementation pending Phase 2 (EC2 Operations)"
        )

    async def delete_instance(self, external_id: str) -> None:
        """Terminate an EC2 instance (stub for Phase 2 implementation).

        Args:
            external_id: AWS EC2 instance ID (e.g., i-1234567890abcdef0)

        Raises:
            NotImplementedError: Full implementation in Phase 2
        """
        raise NotImplementedError(
            "delete_instance implementation pending Phase 2 (EC2 Operations)"
        )

    async def get_instance(self, external_id: str) -> Optional[CloudInstance]:
        """Get EC2 instance details (stub for Phase 2 implementation).

        Args:
            external_id: AWS EC2 instance ID

        Returns:
            CloudInstance with current state, or None if not found

        Raises:
            NotImplementedError: Full implementation in Phase 2
        """
        raise NotImplementedError(
            "get_instance implementation pending Phase 2 (EC2 Operations)"
        )

    async def wait_for_started(
        self, external_id: str, backoff: int = 15, limit: int = 40
    ) -> CloudInstance:
        """Wait for EC2 instance to reach running state.

        Args:
            external_id: AWS EC2 instance ID
            backoff: Seconds between status checks (default: 15)
            limit: Maximum number of retry attempts (default: 40)

        Returns:
            CloudInstance in RUNNING state

        Raises:
            TimeoutError: If instance doesn't reach running state within limit
            NotImplementedError: Full implementation in Phase 4
        """
        raise NotImplementedError(
            "wait_for_started implementation pending Phase 4 (Wait Logic)"
        )

    async def wait_for_public_ip(
        self, external_id: str, backoff: int = 15, limit: int = 20
    ) -> CloudInstance:
        """Wait for EC2 instance to receive public IP address.

        Args:
            external_id: AWS EC2 instance ID
            backoff: Seconds between checks (default: 15)
            limit: Maximum number of retry attempts (default: 20)

        Returns:
            CloudInstance with public IP assigned

        Raises:
            TimeoutError: If public IP not assigned within limit
            NotImplementedError: Full implementation in Phase 4
        """
        raise NotImplementedError(
            "wait_for_public_ip implementation pending Phase 4 (Wait Logic)"
        )

    async def create_ssh_key(self, worker_name: str, public_key: str) -> str:
        """Import SSH public key to AWS EC2 as a key pair.

        Generates a unique key pair name and imports the provided public key
        to AWS EC2 using the import_key_pair API. Checks for existing keys
        to prevent duplicates and applies AWS tags for resource management.

        Args:
            worker_name: Name of the worker (used in key naming)
            public_key: SSH public key in OpenSSH format (e.g., ssh-ed25519 AAAAC3...)

        Returns:
            AWS key pair name (the identifier used for instance creation)

        Raises:
            RuntimeError: If key already exists, key format is invalid, or API call fails
        """
        # Generate key name with random suffix for uniqueness
        suffix = secrets.token_hex(4)  # 8-character hex suffix
        key_name = f"gpustack-{worker_name}-{suffix}"

        async with self._get_client() as client:
            # Check if key already exists to prevent duplicate errors
            exists, fingerprint = await self._check_key_exists(client, key_name)
            if exists:
                raise RuntimeError(
                    f"Key pair '{key_name}' already exists in AWS. "
                    f"Fingerprint: {fingerprint}. "
                    "Please delete the existing key or use a different worker name."
                )

            # Import the public key
            try:
                response = await client.import_key_pair(
                    KeyName=key_name,
                    PublicKeyMaterial=public_key.encode("utf-8"),
                    TagSpecifications=[
                        {
                            "ResourceType": "key-pair",
                            "Tags": [
                                {"Key": "ManagedBy", "Value": "GPUStack"},
                                {"Key": "WorkerName", "Value": worker_name},
                            ],
                        }
                    ],
                )

                imported_fingerprint = response.get("KeyFingerprint")
                logger.info(
                    f"Imported SSH key '{key_name}' to AWS. "
                    f"Fingerprint: {imported_fingerprint}"
                )
                return response["KeyName"]

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "InvalidKey.Format":
                    raise RuntimeError(
                        "Invalid SSH public key format. "
                        "AWS requires OpenSSH format (ssh-ed25519 AAAAC3... or ssh-rsa AAAAB3...)"
                    ) from e
                elif error_code == "InvalidKeyPair.Duplicate":
                    raise RuntimeError(
                        f"Key pair '{key_name}' already exists in AWS"
                    ) from e
                raise self._handle_aws_error(e, "SSH key import")

    async def delete_ssh_key(self, id: str) -> None:
        """Delete EC2 key pair (stub for Phase 2 implementation).

        Args:
            id: AWS key pair name or ID

        Raises:
            NotImplementedError: Full implementation in Phase 2
        """
        raise NotImplementedError(
            "delete_ssh_key implementation pending Phase 2 (EC2 Operations)"
        )

    async def create_volumes_and_attach(
        self, worker_id: int, external_id: str, region: str, *volumes: Volume
    ) -> List[str]:
        """Create EBS volumes and attach to EC2 instance.

        Args:
            worker_id: Internal worker ID for naming
            external_id: AWS EC2 instance ID
            region: AWS region
            volumes: Volume specifications

        Returns:
            List of AWS EBS volume IDs

        Raises:
            NotImplementedError: Full implementation in Phase 5
        """
        raise NotImplementedError(
            "create_volumes_and_attach implementation pending Phase 5 (Storage)"
        )

    async def construct_user_data(
        self,
        server_url: str,
        token: str,
        image_name: str,
        os_image: str,
        secret_configs: Dict[str, Any] = {},
    ) -> Any:
        """Construct user data for EC2 instance initialization.

        Args:
            server_url: GPUStack server URL
            token: Authentication token
            image_name: Name of the image
            os_image: OS image identifier (AMI ID)
            secret_configs: Additional secret configuration

        Returns:
            UserDataTemplate for EC2 user data

        Raises:
            NotImplementedError: Full implementation in Phase 6
        """
        raise NotImplementedError(
            "construct_user_data implementation pending Phase 6 (Integration)"
        )

    @classmethod
    def get_api_endpoint(cls) -> str:
        """Get AWS EC2 API endpoint.

        Note: This returns a placeholder as the actual endpoint
        is region-specific and handled by aiobotocore.

        Returns:
            AWS EC2 service URL
        """
        return "https://ec2.amazonaws.com"

    @classmethod
    def process_header(cls, ak: str, sk: str, options: dict, headers: dict) -> dict:
        """Process headers for AWS API requests.

        AWS uses AWS Signature Version 4 for authentication,
        which is handled internally by aiobotocore. This method
        exists for interface compatibility.

        Args:
            ak: Access key (not used directly, aiobotocore handles auth)
            sk: Secret key (not used directly, aiobotocore handles auth)
            options: Additional options
            headers: Headers dict to modify

        Returns:
            Modified headers dict
        """
        # AWS authentication is handled by aiobotocore's SigV4 signing
        # No manual header manipulation needed
        return headers
