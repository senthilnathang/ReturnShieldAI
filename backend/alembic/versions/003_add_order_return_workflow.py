"""add order return workflow fields

Revision ID: 003
Revises: 002
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("return_requests", sa.Column("created_by", sa.String(length=255), nullable=True))
    op.add_column("return_requests", sa.Column("return_reason_category", sa.String(length=100), nullable=True))
    op.add_column("return_requests", sa.Column("detailed_description", sa.Text(), nullable=True))
    op.add_column("return_requests", sa.Column("return_method", sa.String(length=50), nullable=True))
    op.add_column("return_requests", sa.Column("pickup_address_id", sa.String(length=255), nullable=True))
    op.add_column("return_requests", sa.Column("preferred_refund_method", sa.String(length=50), nullable=True))
    op.add_column("return_requests", sa.Column("fraud_screening_status", sa.String(length=50), nullable=True))
    op.add_column("return_requests", sa.Column("eligibility_override", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("return_requests", sa.Column("eligibility_override_reason", sa.Text(), nullable=True))

    op.add_column("return_items", sa.Column("quantity", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("return_items", sa.Column("product_value", sa.Numeric(12, 2), nullable=True))

    op.create_index("idx_return_requests_created_by", "return_requests", ["created_by"])
    op.create_index("idx_return_requests_reason_category", "return_requests", ["return_reason_category"])
    op.create_index("idx_return_requests_return_method", "return_requests", ["return_method"])
    op.create_index("idx_return_requests_pickup_address_id", "return_requests", ["pickup_address_id"])
    op.create_index("idx_return_requests_refund_method", "return_requests", ["preferred_refund_method"])
    op.create_index("idx_return_requests_fraud_screening_status", "return_requests", ["fraud_screening_status"])
    op.create_index("idx_return_requests_eligibility_override", "return_requests", ["eligibility_override"])


def downgrade() -> None:
    op.drop_index("idx_return_requests_eligibility_override", table_name="return_requests")
    op.drop_index("idx_return_requests_fraud_screening_status", table_name="return_requests")
    op.drop_index("idx_return_requests_refund_method", table_name="return_requests")
    op.drop_index("idx_return_requests_pickup_address_id", table_name="return_requests")
    op.drop_index("idx_return_requests_return_method", table_name="return_requests")
    op.drop_index("idx_return_requests_reason_category", table_name="return_requests")
    op.drop_index("idx_return_requests_created_by", table_name="return_requests")

    op.drop_column("return_items", "product_value")
    op.drop_column("return_items", "quantity")

    op.drop_column("return_requests", "eligibility_override_reason")
    op.drop_column("return_requests", "eligibility_override")
    op.drop_column("return_requests", "fraud_screening_status")
    op.drop_column("return_requests", "preferred_refund_method")
    op.drop_column("return_requests", "pickup_address_id")
    op.drop_column("return_requests", "return_method")
    op.drop_column("return_requests", "detailed_description")
    op.drop_column("return_requests", "return_reason_category")
    op.drop_column("return_requests", "created_by")
