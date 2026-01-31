"""AWS EC2 cloud provider client using aiobotocore.

This module implements the ProviderClientBase interface for AWS EC2,
providing async operations for GPU instance lifecycle management.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any

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

    def _handle_aws_error(self, error: Exception, operation: str) -> None:
        """Convert AWS exceptions to user-friendly error messages.

        Args:
            error: The exception raised by AWS SDK
            operation: Description of the operation being performed

        Raises:
            RuntimeError: With user-friendly message wrapping the original error
        """
        if isinstance(error, ClientError):
            error_code = error.response["Error"]["Code"]
            error_msg = error.response["Error"]["Message"]
            logger.error(f"AWS {operation} failed: {error_code} - {error_msg}")
            raise RuntimeError(f"AWS {operation} failed: {error_code}") from error
        elif isinstance(error, NoCredentialsError):
            logger.error(f"AWS credentials invalid for {operation}")
            raise RuntimeError(
                "Invalid AWS credentials. Please check your access key and secret key."
            ) from error
        elif isinstance(error, EndpointConnectionError):
            logger.error(f"AWS connection failed for {operation}: {error}")
            raise RuntimeError(
                f"Cannot connect to AWS EC2 in region {self.region}. "
                "Please check your network connection."
            ) from error
        else:
            logger.error(f"Unexpected error during {operation}: {error}")
            raise

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
        except ClientError as e:
            self._handle_aws_error(e, "credential validation")
        except NoCredentialsError as e:
            self._handle_aws_error(e, "credential validation")
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
        """Create EC2 key pair (stub for Phase 2 implementation).

        Args:
            worker_name: Name for the key pair
            public_key: SSH public key material

        Returns:
            AWS key pair ID

        Raises:
            NotImplementedError: Full implementation in Phase 2
        """
        raise NotImplementedError(
            "create_ssh_key implementation pending Phase 2 (EC2 Operations)"
        )

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
