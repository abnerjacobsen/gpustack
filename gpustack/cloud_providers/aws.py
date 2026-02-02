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
from .aws_ami_mapping import get_ami_for_region
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
        """Create an EC2 GPU instance with Deep Learning AMI and GPUStack bootstrap.

        Launches an EC2 instance with:
        - Deep Learning AMI for the region (pre-installed NVIDIA drivers, CUDA)
        - User data (cloud-init) for GPUStack worker bootstrap
        - AWS tags for resource management (Name, ManagedBy, GPUStackWorker)
        - Optional custom labels as additional tags
        - Network configuration (subnet, security group) from AWSConfig

        Args:
            instance: CloudInstanceCreate with instance specifications
                - name: Instance name (becomes Name tag)
                - type: EC2 instance type (e.g., "p3.2xlarge", "g4dn.xlarge")
                - region: AWS region (must be in DLAMI mapping)
                - ssh_key_id: AWS key pair name from create_ssh_key
                - user_data: Cloud-init script for worker bootstrap
                - labels: Optional dict of custom tags

        Returns:
            str: Instance ID (e.g., "i-1234567890abcdef0") on success
            None: If creation failed (though typically raises RuntimeError)

        Raises:
            RuntimeError: If AWS API call fails, including:
                - InvalidAMIID.NotFound: AMI not available in region
                - InsufficientInstanceCapacity: GPU instance unavailable
                - VcpuLimitExceeded: Service quota exceeded
                - Other AWS ClientError conditions

        Example:
            >>> instance_spec = CloudInstanceCreate(
            ...     name="gpustack-worker-1",
            ...     type="g4dn.xlarge",
            ...     region="us-east-1",
            ...     ssh_key_id="gpustack-worker-abc123",
            ...     user_data=cloud_init_script,
            ...     labels={"project": "ml-training", "team": "ai"}
            ... )
            >>> instance_id = await aws_client.create_instance(instance_spec)
            >>> print(instance_id)
            i-0abcd1234efgh5678i
        """
        # Get AMI ID for the region (Deep Learning AMI with GPU support)
        ami_id = get_ami_for_region(instance.region)

        # Build base run_instances arguments
        run_args = {
            "ImageId": ami_id,
            "InstanceType": instance.type,
            "KeyName": instance.ssh_key_id,
            "MinCount": 1,
            "MaxCount": 1,
            "UserData": instance.user_data if instance.user_data else "",
        }

        # Build tags for the instance
        base_tags = [
            {"Key": "Name", "Value": instance.name},
            {"Key": "ManagedBy", "Value": "GPUStack"},
            {"Key": "GPUStackWorker", "Value": "true"},
        ]

        # Add custom labels as tags if provided
        if instance.labels:
            for key, value in instance.labels.items():
                base_tags.append({"Key": key, "Value": value})

        run_args["TagSpecifications"] = [
            {"ResourceType": "instance", "Tags": base_tags}
        ]

        # Configure network settings from AWSConfig if available
        if self.config:
            if self.config.subnet_id:
                # Use NetworkInterfaces for subnet with public IP assignment
                network_interface = {
                    "SubnetId": self.config.subnet_id,
                    "DeviceIndex": 0,
                    "AssociatePublicIpAddress": True,
                }

                # Add security group if configured
                if self.config.security_group_id:
                    network_interface["Groups"] = [self.config.security_group_id]

                run_args["NetworkInterfaces"] = [network_interface]
            elif self.config.security_group_id:
                # Security group without subnet (uses default VPC)
                run_args["SecurityGroupIds"] = [self.config.security_group_id]

        # Launch the EC2 instance
        async with self._get_client() as client:
            try:
                response = await client.run_instances(**run_args)
                instance_id = response["Instances"][0]["InstanceId"]
                logger.info(
                    f"Created EC2 instance {instance_id} of type {instance.type} "
                    f"in region {instance.region}"
                )
                return instance_id

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_msg = e.response["Error"]["Message"]

                # Handle specific AWS error codes with user-friendly messages
                if error_code == "InvalidAMIID.NotFound":
                    logger.error(f"AMI {ami_id} not found in region {instance.region}")
                    raise RuntimeError(
                        f"Deep Learning AMI not available in region {instance.region}. "
                        f"AMI ID {ami_id} not found. Please check the AMI mapping "
                        f"or update aws_ami_mapping.py with valid AMI IDs."
                    ) from e

                elif error_code == "InsufficientInstanceCapacity":
                    logger.error(
                        f"GPU instance {instance.type} not available in region "
                        f"{instance.region}: {error_msg}"
                    )
                    raise RuntimeError(
                        f"GPU instance type {instance.type} is currently not "
                        f"available in region {instance.region}. This is a temporary "
                        f"capacity issue. Try again later or use a different "
                        f"instance type or region."
                    ) from e

                elif error_code == "VcpuLimitExceeded":
                    logger.error(
                        f"vCPU limit exceeded for instance type {instance.type}"
                    )
                    raise RuntimeError(
                        f"AWS vCPU service quota exceeded for instance type "
                        f"{instance.type}. Please request a limit increase from "
                        f"AWS Support or use a smaller instance type."
                    ) from e

                elif error_code == "InstanceLimitExceeded":
                    logger.error(f"Instance limit exceeded in region {instance.region}")
                    raise RuntimeError(
                        f"AWS instance limit exceeded in region {instance.region}. "
                        f"Please request a limit increase from AWS Support or "
                        f"terminate unused instances."
                    ) from e

                elif error_code == "InvalidKeyPair.NotFound":
                    logger.error(f"SSH key {instance.ssh_key_id} not found")
                    raise RuntimeError(
                        f"SSH key pair '{instance.ssh_key_id}' not found in AWS. "
                        f"Please create the key pair first using create_ssh_key()."
                    ) from e

                else:
                    # Generic AWS error
                    logger.error(
                        f"Failed to create EC2 instance: {error_code} - {error_msg}"
                    )
                    raise RuntimeError(
                        f"Failed to create EC2 instance: {error_code} - {error_msg}"
                    ) from e

            except Exception as e:
                logger.error(f"Unexpected error creating EC2 instance: {e}")
                raise RuntimeError(f"Failed to create EC2 instance: {str(e)}") from e

    async def delete_instance(self, external_id: str) -> None:
        """Terminate an EC2 instance by ID.

        Args:
            external_id: AWS EC2 instance ID (e.g., i-1234567890abcdef0)

        Note:
            This method is idempotent - if the instance is already terminated
            or does not exist, it logs a warning and returns successfully.
        """
        async with self._get_client() as client:
            try:
                await client.terminate_instances(InstanceIds=[external_id])
                logger.info(f"Terminated EC2 instance {external_id}")
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "InvalidInstanceID.NotFound":
                    logger.warning(
                        f"Instance {external_id} not found in AWS (already deleted or never existed)"
                    )
                    return
                elif error_code == "IncorrectState":
                    # Instance is already terminated or terminating
                    logger.info(
                        f"Instance {external_id} is already in terminated/terminating state"
                    )
                    return
                raise self._handle_aws_error(e, "instance termination")

    async def get_instance(self, external_id: str) -> Optional[CloudInstance]:
        """Get EC2 instance details and status.

        Args:
            external_id: AWS EC2 instance ID

        Returns:
            CloudInstance with current state and details, or None if not found
        """
        async with self._get_client() as client:
            try:
                response = await client.describe_instances(InstanceIds=[external_id])
                reservations = response.get("Reservations", [])
                if not reservations:
                    return None

                instances = reservations[0].get("Instances", [])
                if not instances:
                    return None

                ec2_instance = instances[0]

                # Extract public IP from network interfaces
                public_ip = None
                network_interfaces = ec2_instance.get("NetworkInterfaces", [])
                for eni in network_interfaces:
                    association = eni.get("Association", {})
                    public_ip = association.get("PublicIp")
                    if public_ip:
                        break

                # Alternative: check PublicIpAddress at instance level
                if not public_ip:
                    public_ip = ec2_instance.get("PublicIpAddress")

                # Map AWS state to InstanceState
                aws_state = ec2_instance.get("State", {}).get("Name", "unknown")
                status = status_mapping.get(aws_state, InstanceState.UNKNOWN)

                # Build tags dict from AWS tags
                tags = {}
                for tag in ec2_instance.get("Tags", []):
                    tags[tag["Key"]] = tag["Value"]

                # Get volume IDs from block device mappings
                volume_ids = []
                for bdm in ec2_instance.get("BlockDeviceMappings", []):
                    ebs = bdm.get("Ebs", {})
                    volume_id = ebs.get("VolumeId")
                    if volume_id:
                        volume_ids.append(volume_id)

                return CloudInstance(
                    external_id=ec2_instance.get("InstanceId"),
                    name=tags.get("Name", ""),
                    image=ec2_instance.get("ImageId", ""),
                    type=ec2_instance.get("InstanceType", ""),
                    region=self.region,
                    ssh_key_id=ec2_instance.get("KeyName"),
                    status=status,
                    ip_address=public_ip,
                    volume_ids=volume_ids if volume_ids else None,
                    user_data=None,  # Not returned by describe_instances
                    labels=tags,
                )

            except ClientError as e:
                if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                    logger.debug(f"Instance {external_id} not found")
                    return None
                raise self._handle_aws_error(e, "instance describe")

    async def wait_for_started(
        self, external_id: str, backoff: int = 15, limit: int = 40
    ) -> CloudInstance:
        """Wait for EC2 instance to reach running state.

        Polls the instance status using exponential backoff until the instance
        reaches the RUNNING state. Handles AWS eventual consistency by retrying
        when the instance is not yet visible (InvalidInstanceID.NotFound).

        Args:
            external_id: AWS EC2 instance ID
            backoff: Base seconds between status checks (default: 15)
            limit: Maximum number of retry attempts (default: 40)

        Returns:
            CloudInstance in RUNNING state

        Raises:
            TimeoutError: If instance doesn't reach running state within limit
            RuntimeError: If unexpected error occurs during polling
        """
        for attempt in range(limit):
            instance = await self.get_instance(external_id)

            if instance is None:
                # Instance not yet visible (AWS eventual consistency)
                logger.debug(f"Instance {external_id} not yet visible, retrying...")
            elif instance.status == InstanceState.RUNNING:
                logger.info(
                    f"Instance {external_id} is now running after {attempt + 1} attempts"
                )
                return instance
            else:
                # Log current status for debugging
                logger.debug(
                    f"Waiting for instance {external_id}, attempt {attempt + 1}/{limit}, "
                    f"status: {instance.status.value}"
                )

            # Calculate exponential backoff, capped at 60 seconds
            sleep_time = min(backoff * (2**attempt), 60)
            await asyncio.sleep(sleep_time)

        # Exceeded limit without instance reaching RUNNING
        raise TimeoutError(
            f"EC2 instance {external_id} did not reach running state "
            f"within {limit} attempts ({backoff}s base backoff with exponential increase)"
        )

    async def wait_for_public_ip(
        self, external_id: str, backoff: int = 15, limit: int = 20
    ) -> CloudInstance:
        """Wait for EC2 instance to receive public IP address.

        Polls the instance using exponential backoff until a public IP is assigned.
        Handles AWS eventual consistency by retrying when the instance is not yet
        visible (InvalidInstanceID.NotFound).

        Args:
            external_id: AWS EC2 instance ID
            backoff: Base seconds between checks (default: 15)
            limit: Maximum number of retry attempts (default: 20)

        Returns:
            CloudInstance with public IP assigned

        Raises:
            TimeoutError: If public IP not assigned within limit attempts
            RuntimeError: If unexpected error occurs during polling
        """
        for attempt in range(limit):
            instance = await self.get_instance(external_id)

            if instance is None:
                # Instance not yet visible (AWS eventual consistency)
                logger.debug(f"Instance {external_id} not yet visible, retrying...")
            elif instance.ip_address is not None and instance.ip_address != "":
                # Public IP is assigned
                logger.info(
                    f"Instance {external_id} received public IP {instance.ip_address} "
                    f"after {attempt + 1} attempts"
                )
                return instance
            else:
                # Log current IP status for debugging
                logger.debug(
                    f"Waiting for public IP for instance {external_id}, "
                    f"attempt {attempt + 1}/{limit}, IP: {instance.ip_address}"
                )

            # Calculate exponential backoff, capped at 60 seconds
            sleep_time = min(backoff * (2**attempt), 60)
            await asyncio.sleep(sleep_time)

        # Exceeded limit without IP being assigned
        raise TimeoutError(
            f"EC2 instance {external_id} did not receive a public IP "
            f"within {limit} attempts ({backoff}s base backoff with exponential increase)"
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
        """Delete EC2 key pair by name.

        Args:
            id: AWS key pair name (the 'name' returned by create_ssh_key)

        Note:
            This method is idempotent - if the key doesn't exist,
            it logs a warning and returns successfully.
        """
        async with self._get_client() as client:
            try:
                await client.delete_key_pair(KeyName=id)
                logger.info(f"Deleted SSH key pair '{id}' from AWS")
            except ClientError as e:
                if e.response["Error"]["Code"] == "InvalidKeyPair.NotFound":
                    logger.warning(
                        f"Key pair '{id}' not found in AWS (already deleted)"
                    )
                    return
                raise self._handle_aws_error(e, "SSH key deletion")

    async def _get_instance_az(self, client, instance_id: str) -> str:
        """Get the Availability Zone of an EC2 instance.

        Args:
            client: aiobotocore EC2 client
            instance_id: AWS EC2 instance ID

        Returns:
            Availability Zone string (e.g., "us-east-1a")

        Raises:
            RuntimeError: If instance not found or AZ cannot be determined
        """
        try:
            response = await client.describe_instances(InstanceIds=[instance_id])
            reservations = response.get("Reservations", [])
            if not reservations:
                raise RuntimeError(f"Instance {instance_id} not found")

            instances = reservations[0].get("Instances", [])
            if not instances:
                raise RuntimeError(f"Instance {instance_id} not found in response")

            instance = instances[0]
            state = instance.get("State", {}).get("Name", "unknown")

            # Instance must be running or stopped to attach volumes
            if state not in ["running", "stopped", "pending", "stopping"]:
                raise RuntimeError(
                    f"Instance {instance_id} is in '{state}' state. "
                    "Volumes can only be attached to running or stopped instances."
                )

            az = instance.get("Placement", {}).get("AvailabilityZone")
            if not az:
                raise RuntimeError(
                    f"Could not determine Availability Zone for instance {instance_id}"
                )

            return az

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "InvalidInstanceID.NotFound":
                raise RuntimeError(f"Instance {instance_id} not found in AWS") from e
            raise self._handle_aws_error(e, f"getting AZ for instance {instance_id}")

    async def _create_volume(
        self,
        client,
        az: str,
        worker_id: int,
        idx: int,
        volume: Volume,
    ) -> str:
        """Create an EBS volume with proper tagging and wait for it to be available.

        Args:
            client: aiobotocore EC2 client
            az: Availability Zone (must match instance AZ)
            worker_id: Internal worker ID for naming
            idx: Volume index for naming and device assignment
            volume: Volume specification

        Returns:
            AWS EBS volume ID

        Raises:
            RuntimeError: If volume creation fails
        """
        # Generate volume name
        if volume.name:
            vol_name = f"{volume.name}-{worker_id}"
        else:
            vol_name = f"gpustack-vol-{worker_id}-{idx}"

        # Build tags
        tags = [
            {"Key": "Name", "Value": vol_name},
            {"Key": "ManagedBy", "Value": "GPUStack"},
            {"Key": "WorkerId", "Value": str(worker_id)},
            {"Key": "VolumeIndex", "Value": str(idx)},
            {"Key": "Format", "Value": volume.format},
        ]

        try:
            logger.info(f"Creating EBS volume {vol_name} ({volume.size_gb}GB) in {az}")

            response = await client.create_volume(
                AvailabilityZone=az,
                Size=volume.size_gb,
                VolumeType="gp3",
                Encrypted=True,
                TagSpecifications=[{"ResourceType": "volume", "Tags": tags}],
            )

            volume_id = response.get("VolumeId")
            if not volume_id:
                raise RuntimeError("Volume created but no VolumeId returned")

            logger.info(
                f"Created EBS volume {volume_id} ({volume.size_gb}GB) in {az}, "
                f"waiting for available state"
            )

            # Wait for volume to be available
            waiter = client.get_waiter("volume_available")
            await waiter.wait(VolumeIds=[volume_id])

            logger.info(f"EBS volume {volume_id} is now available")
            return volume_id

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]

            if error_code == "InvalidVolume.ZoneMismatch":
                raise RuntimeError(
                    f"Volume AZ mismatch: {error_msg}. "
                    "Volumes must be created in the same AZ as the instance."
                ) from e
            elif error_code == "VolumeLimitExceeded":
                raise RuntimeError(
                    f"EBS volume limit exceeded: {error_msg}. "
                    "Please request a limit increase from AWS."
                ) from e

            raise self._handle_aws_error(e, f"creating EBS volume {vol_name}")

    async def _attach_volume(
        self,
        client,
        volume_id: str,
        instance_id: str,
        idx: int,
    ) -> None:
        """Attach an EBS volume to an EC2 instance.

        Args:
            client: aiobotocore EC2 client
            volume_id: AWS EBS volume ID
            instance_id: AWS EC2 instance ID
            idx: Volume index for device naming (0=/dev/sdf, 1=/dev/sdg, etc.)

        Raises:
            RuntimeError: If attachment fails

        Note:
            Device names use /dev/sd[f-p] pattern (up to 11 additional volumes)
        """
        # Generate device name: /dev/sdf for idx=0, /dev/sdg for idx=1, etc.
        # Maximum 11 additional volumes supported (/dev/sdf to /dev/sdp)
        if idx < 0 or idx > 10:
            raise ValueError(
                f"Volume index {idx} exceeds maximum of 10 "
                "(only 11 additional volumes supported per instance)"
            )

        device = f"/dev/sd{chr(ord('f') + idx)}"

        try:
            logger.info(
                f"Attaching volume {volume_id} to instance {instance_id} at {device}"
            )

            await client.attach_volume(
                VolumeId=volume_id,
                InstanceId=instance_id,
                Device=device,
            )

            # Wait for volume to be in-use
            waiter = client.get_waiter("volume_in_use")
            await waiter.wait(VolumeIds=[volume_id])

            logger.info(
                f"Successfully attached volume {volume_id} to instance {instance_id} at {device}"
            )

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]

            if error_code == "AttachmentLimitExceeded":
                raise RuntimeError(
                    f"Volume attachment limit exceeded: {error_msg}. "
                    "EC2 instances have a limit on attached volumes."
                ) from e
            elif error_code == "InvalidParameterValue":
                raise RuntimeError(
                    f"Invalid parameter for volume attachment: {error_msg}"
                ) from e
            elif error_code == "IncorrectState":
                raise RuntimeError(
                    f"Volume or instance in incorrect state: {error_msg}. "
                    "Instance may be terminated or volume may be in use elsewhere."
                ) from e

            raise self._handle_aws_error(
                e, f"attaching volume {volume_id} to instance {instance_id}"
            )

    async def _delete_volume(self, client, volume_id: str) -> None:
        """Delete an EBS volume (cleanup helper).

        Args:
            client: aiobotocore EC2 client
            volume_id: AWS EBS volume ID to delete

        Note:
            This method logs warnings on failure but does not raise exceptions,
            as it's typically used for cleanup during error handling.
        """
        try:
            logger.info(f"Deleting EBS volume {volume_id}")
            await client.delete_volume(VolumeId=volume_id)
            logger.info(f"Successfully deleted EBS volume {volume_id}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            logger.warning(
                f"Failed to delete volume {volume_id} during cleanup: "
                f"{error_code} - {error_msg}"
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error deleting volume {volume_id} during cleanup: {e}"
            )

    async def create_volumes_and_attach(
        self, worker_id: int, external_id: str, region: str, *volumes: Volume
    ) -> List[str]:
        """Create EBS volumes and attach to EC2 instance.

        Creates EBS volumes in the same Availability Zone as the instance,
        waits for them to be available, attaches them with proper device naming,
        and waits for attachment to complete.

        Args:
            worker_id: Internal worker ID for naming and tagging
            external_id: AWS EC2 instance ID
            region: AWS region
            volumes: Volume specifications (size_gb, format, optional name)

        Returns:
            List of AWS EBS volume IDs

        Raises:
            ValueError: If volume specifications are invalid
            RuntimeError: If volume creation or attachment fails

        Example:
            >>> volumes = [
            ...     Volume(size_gb=100, format="ext4", name="data"),
            ...     Volume(size_gb=500, format="xfs", name="models"),
            ... ]
            >>> vol_ids = await client.create_volumes_and_attach(
            ...     worker_id=1,
            ...     external_id="i-0abcd1234efgh5678i",
            ...     region="us-east-1",
            ...     *volumes
            ... )
            >>> print(vol_ids)
            ['vol-0123456789abcdef0', 'vol-0987654321fedcba0']
        """
        # Return early if no volumes
        if not volumes:
            return []

        volume_ids = []
        created_volumes = []  # Track for cleanup on failure

        async with self._get_client() as client:
            # Step 1: Get the instance's Availability Zone
            az = await self._get_instance_az(client, external_id)
            logger.info(f"Instance {external_id} is in AZ {az}, creating volumes there")

            # Step 2: Validate all volumes first
            for idx, volume in enumerate(volumes):
                # Validate size_gb
                if volume.size_gb is None or volume.size_gb <= 0:
                    raise ValueError(
                        f"Volume #{idx} missing or invalid 'size_gb': {volume}"
                    )

                # Validate format
                if volume.format is None or volume.format not in ["ext4", "xfs"]:
                    raise ValueError(
                        f"Volume #{idx} has invalid 'format': {volume.format}. "
                        f"Must be 'ext4' or 'xfs'"
                    )

            # Step 3: Create and attach volumes
            for idx, volume in enumerate(volumes):
                vol_id = None
                try:
                    # Create volume
                    vol_id = await self._create_volume(
                        client, az, worker_id, idx, volume
                    )
                    created_volumes.append(vol_id)

                    # Attach volume
                    await self._attach_volume(client, vol_id, external_id, idx)
                    volume_ids.append(vol_id)

                except Exception:
                    # Cleanup: delete any volumes we created but failed to attach
                    if vol_id:
                        await self._delete_volume(client, vol_id)
                        # Remove from created_volumes since we deleted it
                        if vol_id in created_volumes:
                            created_volumes.remove(vol_id)

                    # Also cleanup any previously created volumes
                    for cleanup_vol_id in created_volumes:
                        await self._delete_volume(client, cleanup_vol_id)

                    raise

        logger.info(
            f"Successfully created and attached {len(volume_ids)} volumes to instance {external_id}"
        )
        return volume_ids

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

    async def get_regions(self) -> List[dict]:
        """List all AWS regions using aiobotocore.

        Calls EC2 describe_regions() and returns a list of regions
        in a format compatible with the frontend.

        Returns:
            List of region dictionaries with keys: slug, name, endpoint, opt_in_status
        """
        logger.debug("[AWSClient] Getting regions list")

        async with self._get_client() as client:
            response = await client.describe_regions()

            regions = []
            for region_data in response.get("Regions", []):
                region_name = region_data.get("RegionName", "")
                endpoint = region_data.get("Endpoint", "")
                opt_in_status = region_data.get("OptInStatus", "opt-in-not-required")

                regions.append(
                    {
                        "slug": region_name,
                        "name": region_name,
                        "endpoint": endpoint,
                        "opt_in_status": opt_in_status,
                        "available": opt_in_status == "opt-in-not-required",
                    }
                )

            logger.info(f"[AWSClient] Retrieved {len(regions)} regions")
            return regions

    async def get_images(self, region: Optional[str] = None) -> List[dict]:
        """List Deep Learning AMIs using aiobotocore.

        Calls EC2 describe_images() with filters for AWS Deep Learning AMIs
        and returns a list of images compatible with the frontend.

        Args:
            region: Optional region to filter. Uses client's region if not specified.

        Returns:
            List of image dictionaries with AMI details
        """
        target_region = region or self.region
        logger.debug(
            f"[AWSClient] Getting Deep Learning AMIs for region {target_region}"
        )

        # Filter for AWS Deep Learning AMIs (Ubuntu-based, GPU-enabled)
        filters = [
            {"Name": "name", "Values": ["Deep Learning AMI GPU *"]},
            {"Name": "owner-alias", "Values": ["amazon"]},
            {"Name": "architecture", "Values": ["x86_64"]},
            {"Name": "virtualization-type", "Values": ["hvm"]},
            {"Name": "root-device-type", "Values": ["ebs"]},
        ]

        async with self._get_client() as client:
            response = await client.describe_images(Owners=["amazon"], Filters=filters)

            images = []
            for image_data in response.get("Images", []):
                ami_id = image_data.get("ImageId", "")
                name = image_data.get("Name", "")
                description = image_data.get("Description", "")
                created_at = image_data.get("CreationDate", "")

                # Extract volume size from block device mappings
                bd_mappings = image_data.get("BlockDeviceMappings", [])
                size_gb = 100  # default
                if bd_mappings:
                    ebs = bd_mappings[0].get("Ebs", {})
                    size_gb = ebs.get("VolumeSize", 100)

                images.append(
                    {
                        "id": ami_id,
                        "name": name,
                        "description": description,
                        "slug": ami_id,
                        "distribution": "Ubuntu",
                        "regions": [target_region],
                        "created_at": created_at,
                        "type": "snapshot",
                        "min_disk_size": size_gb,
                        "size_gigabytes": size_gb,
                    }
                )

            logger.info(f"[AWSClient] Retrieved {len(images)} AMIs")
            return images

    async def get_instance_types(self, gpu_only: bool = True) -> List[dict]:
        """List EC2 instance types using aiobotocore.

        Calls EC2 describe_instance_types() and returns GPU-enabled
        instance types (p3, p4d, g4dn, g5 families).

        Args:
            gpu_only: If True, only return GPU-enabled instance types

        Returns:
            List of instance type dictionaries with specs
        """
        logger.debug("[AWSClient] Getting instance types")

        instance_types = []
        next_token = None

        # Build filters for GPU instance types
        if gpu_only:
            filters = [
                {
                    "Name": "instance-type",
                    "Values": [
                        "p3.*",
                        "p3dn.*",  # Tesla V100
                        "p4d.*",
                        "p4de.*",  # A100
                        "g4dn.*",  # T4
                        "g5.*",
                        "g5g.*",  # A10G / A100 (Graviton)
                    ],
                }
            ]
        else:
            filters = []

        async with self._get_client() as client:
            while True:
                kwargs = {}
                if filters:
                    kwargs["Filters"] = filters
                if next_token:
                    kwargs["NextToken"] = next_token

                response = await client.describe_instance_types(**kwargs)

                for it_data in response.get("InstanceTypes", []):
                    instance_type = it_data.get("InstanceType", "")

                    # Get GPU info
                    gpu_info = it_data.get("GpuInfo", {})
                    gpus = gpu_info.get("Gpus", [])
                    total_gpu_memory = sum(
                        gpu.get("MemoryInfo", {}).get("SizeInMiB", 0) for gpu in gpus
                    )

                    # Get vCPU and memory
                    vcpu_info = it_data.get("VCpuInfo", {})
                    vcpu_count = vcpu_info.get("DefaultVCpus", 0)

                    memory_info = it_data.get("MemoryInfo", {})
                    memory_mib = memory_info.get("SizeInMiB", 0)

                    # Build description
                    gpu_names = [gpu.get("Name", "Unknown") for gpu in gpus]
                    description = f"{vcpu_count} vCPUs, {memory_mib / 1024:.1f} GB RAM"
                    if gpus:
                        description += f", {len(gpus)} GPU(s) ({', '.join(gpu_names)})"

                    instance_types.append(
                        {
                            "slug": instance_type,
                            "description": description,
                            "available": True,
                            "features": ["gpu", "nvidia"] if gpus else [],
                            "gpu_info": (
                                {
                                    "gpu_count": len(gpus),
                                    "gpu_memory_mib": total_gpu_memory,
                                    "gpu_types": gpu_names,
                                }
                                if gpus
                                else None
                            ),
                            "vcpu_count": vcpu_count,
                            "memory_mib": memory_mib,
                            "network_performance": it_data.get("NetworkInfo", {}).get(
                                "NetworkPerformance", "Unknown"
                            ),
                        }
                    )

                next_token = response.get("NextToken")
                if not next_token:
                    break

        logger.info(f"[AWSClient] Retrieved {len(instance_types)} instance types")
        return instance_types

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
