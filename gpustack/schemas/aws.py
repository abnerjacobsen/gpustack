"""AWS configuration schema for GPUStack cloud provider.

This module defines the AWS configuration model used for validating
and storing AWS provider-specific settings.
"""

import re
from typing import Optional
from pydantic import BaseModel, field_validator, ConfigDict, SecretStr


class AWSConfig(BaseModel):
    """AWS cloud provider configuration schema.

    Defines the configuration required for AWS EC2 GPU instance provisioning.
    Sensitive fields (secret_key) are handled securely using SecretStr.

    Required fields:
        - access_key: AWS access key ID (e.g., AKIA...)
        - secret_key: AWS secret access key (sensitive, stored as SecretStr)
        - region: AWS region (e.g., us-east-1, eu-west-1)

    Optional fields:
        - vpc_id: VPC ID for instance placement
        - subnet_id: Subnet ID for instance placement
        - security_group_id: Security group ID for network rules
    """

    model_config = ConfigDict(extra="ignore")

    # Required fields
    access_key: str
    secret_key: SecretStr
    region: str

    # Optional fields
    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None
    security_group_id: Optional[str] = None

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate AWS region format (lowercase with hyphens)."""
        if not v:
            raise ValueError("Region cannot be empty")
        # AWS regions follow pattern: us-east-1, eu-west-2, ap-southeast-1
        if not re.match(r"^[a-z]{2}-[a-z]+-\d$", v):
            raise ValueError(
                f"Invalid AWS region format: {v}. "
                "Expected format: us-east-1, eu-west-1, ap-southeast-1"
            )
        return v

    @field_validator("access_key")
    @classmethod
    def validate_access_key(cls, v: str) -> str:
        """Validate AWS access key ID format.

        AWS access keys typically start with AKIA for long-term credentials
        or ASIA for temporary credentials, followed by 16 alphanumeric chars.
        """
        if not v:
            raise ValueError("Access key cannot be empty")
        # Basic format validation - AWS keys are alphanumeric, 20 chars
        # Start with AKIA (long-term) or ASIA (temporary)
        if not re.match(r"^(AKIA|ASIA)[A-Z0-9]{16}$", v):
            raise ValueError(
                f"Invalid AWS access key format. "
                "Expected 20-character alphanumeric string starting with AKIA or ASIA"
            )
        return v
