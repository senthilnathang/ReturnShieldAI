"""add model training runs

Revision ID: 002
Revises: 001
Create Date: 2026-07-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "model_training_runs" in inspector.get_table_names():
        return
    op.create_table(
        "model_training_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_name", sa.String(100), nullable=False, index=True),
        sa.Column("model_type", sa.String(100), nullable=False, index=True),
        sa.Column("version", sa.String(64), nullable=False, index=True),
        sa.Column("accuracy", sa.Float(), server_default="0"),
        sa.Column("precision", sa.Float(), server_default="0", index=True),
        sa.Column("recall", sa.Float(), server_default="0", index=True),
        sa.Column("f1", sa.Float(), server_default="0", index=True),
        sa.Column("roc_auc", sa.Float(), server_default="0"),
        sa.Column("pr_auc", sa.Float(), server_default="0", index=True),
        sa.Column("false_positive_rate", sa.Float(), server_default="0"),
        sa.Column("false_negative_rate", sa.Float(), server_default="0"),
        sa.Column("training_time_seconds", sa.Float(), server_default="0"),
        sa.Column("prediction_latency_ms", sa.Float(), server_default="0"),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("metrics_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_best", sa.Boolean(), server_default=sa.text("false"), index=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("model_training_runs")
