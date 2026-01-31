"""Unit tests for AWSClient using moto for AWS API mocking.

This module contains tests for AWSClient credential validation and initialization,
using moto's mock_aws decorator to simulate AWS EC2 API responses.
"""

import pytest
from moto import mock_aws
from botocore.exceptions import ClientError
from gpustack.cloud_providers.aws import AWSClient
from gpustack.cloud_providers.common import generate_ssh_key_pair


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
