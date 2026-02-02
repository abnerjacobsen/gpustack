"""add aws to clusterprovider enum

Revision ID: a1b2c3d4e5f6
Revises: 1a2b3c4d5e6f
Create Date: 2026-02-02 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import gpustack.utils.sql_enum as sql_enum

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the current enum state (as it exists before this migration)
cluster_provider_enum = sa.Enum(
    "Docker",
    "Kubernetes",
    "DigitalOcean",
    name="clusterprovider",
)

# Value to add
to_add_value = "AWS"

# Tables and columns that use this enum
table_columns = {
    "cloud_credentials": "provider",
    "clusters": "provider",
}

downgrade_cluster_provider_enum = sa.Enum(
    "Docker",
    "Kubernetes",
    "DigitalOcean",
    "AWS",
    name="clusterprovider",
)

def upgrade() -> None:
    """Add AWS to clusterprovider enum."""
    sql_enum.add_enum_values(
        table_columns,
        cluster_provider_enum,
        to_add_value,
    )


def downgrade() -> None:
    """Remove AWS from clusterprovider enum."""
    # Note: PostgreSQL doesn't support removing values from enums easily
    # This would require creating a new enum, converting columns, and dropping the old one
    # For now, we skip the downgrade or document that it's not reversible
    sql_enum.remove_enum_values(
        table_columns,
        downgrade_cluster_provider_enum,
        to_add_value,
    )
