"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # merchants
    op.create_table(
        "merchants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("risk_threshold_low", sa.Integer(), server_default="40"),
        sa.Column("risk_threshold_high", sa.Integer(), server_default="70"),
        sa.Column("settings_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # customers
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("external_customer_id", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("email_hash", sa.String(128), nullable=True, index=True),
        sa.Column("phone_hash", sa.String(128), nullable=True, index=True),
        sa.Column("account_age_days", sa.Integer(), server_default="0"),
        sa.Column("lifetime_orders", sa.Integer(), server_default="0"),
        sa.Column("lifetime_returns", sa.Integer(), server_default="0"),
        sa.Column("lifetime_refunds", sa.Numeric(12, 2), nullable=True),
        sa.Column("customer_risk_score", sa.Integer(), server_default="0", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # customer_identities
    op.create_table(
        "customer_identities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("identity_type", sa.String(50), nullable=False),
        sa.Column("identity_value_hash", sa.String(128), nullable=False, index=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_index("idx_customer_identities_lookup", "customer_identities", ["merchant_id", "identity_type", "identity_value_hash"])

    # orders
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("external_order_id", sa.String(255), nullable=True, index=True),
        sa.Column("sku", sa.String(100), nullable=True, index=True),
        sa.Column("product_name", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("product_value", sa.Numeric(12, 2), nullable=True, index=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("payment_method_risk_score", sa.Integer(), server_default="0"),
        sa.Column("order_status", sa.String(50), nullable=True),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # shipments
    op.create_table(
        "shipments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("carrier", sa.String(100), nullable=True, index=True),
        sa.Column("tracking_number_hash", sa.String(128), nullable=True, index=True),
        sa.Column("delivery_status", sa.String(50), nullable=True),
        sa.Column("delivery_address_hash", sa.String(128), nullable=True, index=True),
        sa.Column("pickup_address_hash", sa.String(128), nullable=True, index=True),
        sa.Column("expected_weight", sa.Numeric(10, 3), nullable=True),
        sa.Column("scanned_delivery_weight", sa.Numeric(10, 3), nullable=True),
        sa.Column("returned_weight", sa.Numeric(10, 3), nullable=True),
        sa.Column("weight_difference", sa.Numeric(10, 3), nullable=True, index=True),
        sa.Column("delivery_confirmation_type", sa.String(50), nullable=True),
        sa.Column("delivery_photo_url", sa.Text(), nullable=True),
        sa.Column("warehouse_scan_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # return_requests
    op.create_table(
        "return_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("shipment_id", UUID(as_uuid=True), sa.ForeignKey("shipments.id"), nullable=True, index=True),
        sa.Column("external_return_id", sa.String(255), nullable=True, index=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("condition_reported", sa.String(100), nullable=True),
        sa.Column("return_status", sa.String(50), nullable=True, index=True),
        sa.Column("return_channel", sa.String(50), nullable=True),
        sa.Column("return_date", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("hours_after_delivery", sa.Numeric(10, 2), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # return_items
    op.create_table(
        "return_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("return_requests.id"), nullable=False, index=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("sku", sa.String(100), nullable=True, index=True),
        sa.Column("product_name", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("declared_condition", sa.String(100), nullable=True),
        sa.Column("warehouse_condition", sa.String(100), nullable=True),
        sa.Column("serial_number_hash", sa.String(128), nullable=True, index=True),
        sa.Column("imei_hash", sa.String(128), nullable=True, index=True),
        sa.Column("item_match_status", sa.String(50), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # payments
    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("payment_token_hash", sa.String(128), nullable=True, index=True),
        sa.Column("upi_hash", sa.String(128), nullable=True, index=True),
        sa.Column("card_bin", sa.String(10), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("chargeback_flag", sa.Boolean(), server_default="false", index=True),
        sa.Column("chargeback_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # refunds
    op.create_table(
        "refunds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("return_requests.id"), nullable=False, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("refund_method", sa.String(50), nullable=True),
        sa.Column("refund_account_hash", sa.String(128), nullable=True, index=True),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("refund_status", sa.String(50), nullable=True, index=True),
        sa.Column("refund_date", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # support_interactions
    op.create_table(
        "support_interactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("return_requests.id"), nullable=True, index=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("message_embedding_id", sa.String(255), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("urgency_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # fraud_scores
    op.create_table(
        "fraud_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("return_requests.id"), nullable=False, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("rule_score", sa.Integer(), server_default="0"),
        sa.Column("structured_ml_score", sa.Integer(), server_default="0"),
        sa.Column("nlp_score", sa.Integer(), server_default="0"),
        sa.Column("graph_score", sa.Integer(), server_default="0"),
        sa.Column("anomaly_score", sa.Integer(), server_default="0"),
        sa.Column("final_score", sa.Integer(), server_default="0", index=True),
        sa.Column("risk_level", sa.String(20), nullable=True, index=True),
        sa.Column("decision", sa.String(50), nullable=True, index=True),
        sa.Column("reason_codes_json", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("score_breakdown_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # fraud_cases
    op.create_table(
        "fraud_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("return_requests.id"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("fraud_score_id", UUID(as_uuid=True), sa.ForeignKey("fraud_scores.id"), nullable=True),
        sa.Column("case_status", sa.String(50), nullable=True, index=True),
        sa.Column("priority", sa.String(20), nullable=True, index=True),
        sa.Column("assigned_to", sa.String(255), nullable=True, index=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("case_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # rules
    op.create_table(
        "rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_expression", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # analyst_feedback
    op.create_table(
        "analyst_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False, index=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("fraud_cases.id"), nullable=False),
        sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("return_requests.id"), nullable=False),
        sa.Column("analyst_decision", sa.String(50), nullable=True),
        sa.Column("confirmed_label", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # import_jobs
    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending", index=True),
        sa.Column("total_rows", sa.Integer(), server_default="0"),
        sa.Column("processed_rows", sa.Integer(), server_default="0"),
        sa.Column("failed_rows", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=True, index=True),
        sa.Column("event_json", JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("import_jobs")
    op.drop_table("analyst_feedback")
    op.drop_table("rules")
    op.drop_table("fraud_cases")
    op.drop_table("fraud_scores")
    op.drop_table("support_interactions")
    op.drop_table("refunds")
    op.drop_table("payments")
    op.drop_table("return_items")
    op.drop_table("return_requests")
    op.drop_table("shipments")
    op.drop_table("orders")
    op.drop_table("customer_identities")
    op.drop_table("customers")
    op.drop_table("merchants")
