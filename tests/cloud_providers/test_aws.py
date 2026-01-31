"""Unit tests for AWSClient using moto for AWS API mocking.

This module contains tests for AWSClient credential validation and initialization,
using moto's mock_aws decorator to simulate AWS EC2 API responses.
"""

import pytest
from moto import mock_aws
from gpustack.cloud_providers.aws import AWSClient


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
