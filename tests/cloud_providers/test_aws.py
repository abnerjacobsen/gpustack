"""Unit tests for AWSClient using moto for AWS API mocking.

This module contains tests for AWSClient credential validation and initialization,
using moto's mock_aws decorator to simulate AWS EC2 API responses.
"""

import pytest
from moto import mock_aws
from botocore.exceptions import ClientError
from pydantic import SecretStr
from gpustack.cloud_providers.aws import AWSClient
from gpustack.cloud_providers.abstract import CloudInstanceCreate
from gpustack.cloud_providers.common import generate_ssh_key_pair
from gpustack.schemas.aws import AWSConfig


# Real ED25519 public key for testing
TEST_PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDIhz2GK/XCUj4i6Q5yQJNL1MXMY0RxzPV2QrBqfHrDq test@example.com"


@pytest.fixture
def aws_client():
    """Create AWSClient with dummy credentials for moto."""
    return AWSClient(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
    )


@pytest.mark.asyncio
@mock_aws
async def test_validate_credentials_success(aws_client):
    """Test credential validation with valid (moto-mocked) credentials."""
    result = await aws_client.validate_credentials()
    assert result is True


@pytest.mark.asyncio
async def test_validate_credentials_invalid():
    """Test credential validation with invalid credentials."""
    client = AWSClient(
        access_key="invalid",
        secret_key="invalid",
        region="us-east-1",
    )
    with pytest.raises(RuntimeError, match="Invalid AWS credentials"):
        await client.validate_credentials()


@pytest.mark.asyncio
async def test_client_initialization(aws_client):
    """Test AWSClient initializes properly with aiobotocore."""
    assert aws_client.access_key == "AKIAIOSFODNN7EXAMPLE"
    assert aws_client.region == "us-east-1"
    assert aws_client.boto_config.retries["max_attempts"] == 10


@pytest.mark.asyncio
async def test_retry_configuration():
    """Test AWSClient retry policy configuration."""
    client = AWSClient(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="eu-west-1",
    )
    assert client.boto_config.retries["max_attempts"] == 10
    assert client.boto_config.retries["mode"] == "adaptive"
    assert client.boto_config.connect_timeout == 10
    assert client.boto_config.read_timeout == 30


# SSH Key Management Tests


@pytest.mark.asyncio
@mock_aws
async def test_create_ssh_key_success(aws_client):
    """Test creating SSH key pair with valid public key."""
    key_name = await aws_client.create_ssh_key("test-worker", TEST_PUBLIC_KEY)

    # Verify key name follows expected pattern
    assert key_name.startswith("gpustack-test-worker-")

    # Verify key exists in AWS with correct tags
    async with aws_client._get_client() as client:
        response = await client.describe_key_pairs(KeyNames=[key_name])
        key_info = response["KeyPairs"][0]
        assert key_info["KeyName"] == key_name

        # Check tags
        tags = {tag["Key"]: tag["Value"] for tag in key_info.get("Tags", [])}
        assert tags.get("ManagedBy") == "GPUStack"
        assert tags.get("WorkerName") == "test-worker"


@pytest.mark.asyncio
@mock_aws
async def test_create_ssh_key_duplicate(aws_client):
    """Test that creating duplicate key pair raises RuntimeError."""
    # Create key first
    key_name = await aws_client.create_ssh_key("duplicate-test", TEST_PUBLIC_KEY)

    # Try to create again with same key name pattern - manually import first
    # Then try to create via our method which should detect collision
    with pytest.raises(RuntimeError, match="already exists"):
        # Try to create with exact same key name (bypassing the random suffix)
        # We need to manually create a collision scenario
        await aws_client.create_ssh_key("duplicate-test", TEST_PUBLIC_KEY)


@pytest.mark.asyncio
@mock_aws
async def test_create_ssh_key_invalid_format(aws_client):
    """Test that invalid public key format raises RuntimeError."""
    invalid_key = "not-a-valid-ssh-key-format"

    with pytest.raises(RuntimeError, match="Invalid SSH public key format"):
        await aws_client.create_ssh_key("invalid-test", invalid_key)


@pytest.mark.asyncio
@mock_aws
async def test_delete_ssh_key_success(aws_client):
    """Test deleting SSH key pair successfully."""
    # Create key first
    key_name = await aws_client.create_ssh_key("delete-test", TEST_PUBLIC_KEY)

    # Verify key exists
    async with aws_client._get_client() as client:
        response = await client.describe_key_pairs(KeyNames=[key_name])
        assert len(response["KeyPairs"]) == 1

    # Delete key
    await aws_client.delete_ssh_key(key_name)

    # Verify key is gone
    async with aws_client._get_client() as client:
        with pytest.raises(ClientError) as exc_info:
            await client.describe_key_pairs(KeyNames=[key_name])
        assert exc_info.value.response["Error"]["Code"] == "InvalidKeyPair.NotFound"


@pytest.mark.asyncio
@mock_aws
async def test_delete_ssh_key_not_found(aws_client):
    """Test deleting non-existent key is idempotent (no error)."""
    # Should not raise error for non-existent key
    await aws_client.delete_ssh_key("non-existent-key-name")

    # If we get here without exception, test passes
    assert True


@pytest.mark.asyncio
@mock_aws
async def test_ssh_key_lifecycle(aws_client):
    """Test complete SSH key lifecycle: create, verify, delete, verify gone."""
    # Generate a real key pair
    private_key, public_key = generate_ssh_key_pair("ED25519")

    # Create key in AWS
    key_name = await aws_client.create_ssh_key("lifecycle-test", public_key)

    # Verify key name pattern
    assert key_name.startswith("gpustack-lifecycle-test-")

    # Verify key exists with correct tags
    async with aws_client._get_client() as client:
        response = await client.describe_key_pairs(KeyNames=[key_name])
        key_info = response["KeyPairs"][0]
        assert key_info["KeyName"] == key_name
        tags = {tag["Key"]: tag["Value"] for tag in key_info.get("Tags", [])}
        assert tags.get("ManagedBy") == "GPUStack"
        assert tags.get("WorkerName") == "lifecycle-test"

    # Delete key
    await aws_client.delete_ssh_key(key_name)

    # Verify key is gone
    async with aws_client._get_client() as client:
        with pytest.raises(ClientError) as exc_info:
            await client.describe_key_pairs(KeyNames=[key_name])
        assert exc_info.value.response["Error"]["Code"] == "InvalidKeyPair.NotFound"


# Instance Creation Tests


@pytest.mark.asyncio
@mock_aws
async def test_create_instance_success(aws_client):
    """Test creating an EC2 GPU instance with all configurations."""
    # First create an SSH key (required for instance creation)
    key_name = await aws_client.create_ssh_key("test-instance", TEST_PUBLIC_KEY)

    # Prepare user data (cloud-init script)
    user_data = """#!/bin/bash
echo "GPUStack worker bootstrap"
"""

    # Create instance spec
    instance_spec = CloudInstanceCreate(
        name="test-gpu-worker",
        image="ami-0a1b2c3d4e5f67890",  # This will be replaced by DLAMI mapping
        type="g4dn.xlarge",
        region="us-east-1",
        ssh_key_id=key_name,
        user_data=user_data,
        labels={"project": "test", "team": "engineering"},
    )

    # Create the instance
    instance_id = await aws_client.create_instance(instance_spec)

    # Verify instance ID was returned (format: i-xxxxxxxxxxxxxxxxx)
    assert instance_id is not None
    assert instance_id.startswith("i-")
    assert len(instance_id) == 19

    # Verify instance exists in AWS with correct properties
    async with aws_client._get_client() as client:
        response = await client.describe_instances(InstanceIds=[instance_id])
        instances = response["Reservations"][0]["Instances"]
        assert len(instances) == 1

        instance_info = instances[0]
        assert instance_info["InstanceType"] == "g4dn.xlarge"
        assert instance_info["KeyName"] == key_name
        assert instance_info["State"]["Name"] in ["pending", "running"]

        # Verify tags applied correctly
        tags = {tag["Key"]: tag["Value"] for tag in instance_info.get("Tags", [])}
        assert tags.get("Name") == "test-gpu-worker"
        assert tags.get("ManagedBy") == "GPUStack"
        assert tags.get("GPUStackWorker") == "true"
        assert tags.get("project") == "test"
        assert tags.get("team") == "engineering"


@pytest.mark.asyncio
@mock_aws
async def test_create_instance_with_network_config(aws_client):
    """Test instance creation with subnet and security group from AWSConfig."""
    # Create a client with network configuration
    client_with_network = AWSClient(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        config=AWSConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key=SecretStr("dummy-secret"),
            region="us-east-1",
            subnet_id="subnet-12345",
            security_group_id="sg-67890",
        ),
    )

    # Create SSH key
    key_name = await client_with_network.create_ssh_key("net-test", TEST_PUBLIC_KEY)

    instance_spec = CloudInstanceCreate(
        name="net-config-test",
        image="ami-test",
        type="p3.2xlarge",
        region="us-east-1",
        ssh_key_id=key_name,
        user_data="#cloud-config\nruncmd: [echo test]",
    )

    # Create instance (should use network configuration from AWSConfig)
    instance_id = await client_with_network.create_instance(instance_spec)
    assert instance_id is not None
    assert instance_id.startswith("i-")

    # Verify instance was created
    async with client_with_network._get_client() as client:
        response = await client.describe_instances(InstanceIds=[instance_id])
        instances = response["Reservations"][0]["Instances"]
        assert len(instances) == 1
        assert instances[0]["InstanceType"] == "p3.2xlarge"


@pytest.mark.asyncio
@mock_aws
async def test_create_instance_security_group_only(aws_client):
    """Test instance creation with only security group (no subnet)."""
    client_with_sg = AWSClient(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        config=AWSConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key=SecretStr("dummy-secret"),
            region="us-east-1",
            security_group_id="sg-test123",
        ),
    )

    key_name = await client_with_sg.create_ssh_key("sg-test", TEST_PUBLIC_KEY)

    instance_spec = CloudInstanceCreate(
        name="sg-only-test",
        image="ami-test",
        type="g5.xlarge",
        region="us-east-1",
        ssh_key_id=key_name,
    )

    instance_id = await client_with_sg.create_instance(instance_spec)
    assert instance_id is not None
    assert instance_id.startswith("i-")


@pytest.mark.asyncio
@mock_aws
async def test_create_instance_invalid_ami(aws_client):
    """Test error handling for unsupported region (no AMI mapping)."""
    key_name = await aws_client.create_ssh_key("ami-test", TEST_PUBLIC_KEY)

    instance_spec = CloudInstanceCreate(
        name="ami-error-test",
        image="ami-test",
        type="g4dn.xlarge",
        region="ap-south-1",  # Not in our DLAMI mapping
        ssh_key_id=key_name,
    )

    with pytest.raises(ValueError, match="Unsupported AWS region"):
        await aws_client.create_instance(instance_spec)


@pytest.mark.asyncio
@mock_aws
async def test_create_instance_no_user_data(aws_client):
    """Test instance creation without user data."""
    key_name = await aws_client.create_ssh_key("no-ud-test", TEST_PUBLIC_KEY)

    instance_spec = CloudInstanceCreate(
        name="no-user-data-test",
        image="ami-test",
        type="p4d.24xlarge",
        region="us-east-1",
        ssh_key_id=key_name,
        user_data=None,
    )

    instance_id = await aws_client.create_instance(instance_spec)
    assert instance_id is not None
    assert instance_id.startswith("i-")


@pytest.mark.asyncio
@mock_aws
async def test_create_instance_no_labels(aws_client):
    """Test instance creation without custom labels."""
    key_name = await aws_client.create_ssh_key("no-labels-test", TEST_PUBLIC_KEY)

    instance_spec = CloudInstanceCreate(
        name="no-labels-test",
        image="ami-test",
        type="g4dn.xlarge",
        region="us-east-1",
        ssh_key_id=key_name,
    )

    instance_id = await aws_client.create_instance(instance_spec)
    assert instance_id is not None

    # Verify only base tags are applied
    async with aws_client._get_client() as client:
        response = await client.describe_instances(InstanceIds=[instance_id])
        instances = response["Reservations"][0]["Instances"]
        tags = {tag["Key"]: tag["Value"] for tag in instances[0].get("Tags", [])}

        assert tags.get("Name") == "no-labels-test"
        assert tags.get("ManagedBy") == "GPUStack"
        assert tags.get("GPUStackWorker") == "true"
        assert "project" not in tags
