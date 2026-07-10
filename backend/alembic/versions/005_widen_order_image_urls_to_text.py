"""widen order image url fields to text

Revision ID: 005
Revises: 004
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("orders", "product_image_url", existing_type=sa.String(length=2048), type_=sa.Text(), existing_nullable=True)
    op.alter_column("orders", "delivery_image_url", existing_type=sa.String(length=2048), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("orders", "delivery_image_url", existing_type=sa.Text(), type_=sa.String(length=2048), existing_nullable=True)
    op.alter_column("orders", "product_image_url", existing_type=sa.Text(), type_=sa.String(length=2048), existing_nullable=True)
