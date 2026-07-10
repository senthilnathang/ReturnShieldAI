"""add order image url fields

Revision ID: 004
Revises: 003
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("product_image_url", sa.String(length=2048), nullable=True))
    op.add_column("orders", sa.Column("delivery_image_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "delivery_image_url")
    op.drop_column("orders", "product_image_url")
