"""Initial schema: users, products, bills, bill_lines, payments, stock_moves.

Revision ID: 0001
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Bill numbers come from a real Postgres sequence so two concurrent sales can
# never be handed the same number (FR-24). It starts at 1042 to match the
# prototype's first order number.
BILL_NO_SEQ_START = 1042


def upgrade() -> None:
    user_role = sa.Enum("MANAGER", "CASHIER", name="user_role")
    stock_move_reason = sa.Enum(
        "OPENING", "RECEIVE", "REMOVE", "SALE", name="stock_move_reason"
    )
    payment_method = sa.Enum("CASH", "UPI", name="payment_method")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("photo_url", sa.String(length=255), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # The database-level backstop for the no-oversell guarantee (TR-01).
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )
    op.create_index("ix_products_category", "products", ["category"])

    op.execute(f"CREATE SEQUENCE bill_no_seq AS bigint START WITH {BILL_NO_SEQ_START}")

    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_no", sa.Integer(), nullable=False, unique=True),
        sa.Column("cashier_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("gst", sa.Numeric(10, 2), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_bills_bill_no", "bills", ["bill_no"])
    op.create_index("ix_bills_created_at", "bills", ["created_at"])

    op.create_table(
        "bill_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_bill_lines_qty_positive"),
    )
    op.create_index("ix_bill_lines_bill_id", "bill_lines", ["bill_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=False, unique=True
        ),
        sa.Column("method", payment_method, nullable=False),
        sa.Column("tendered", sa.Numeric(10, 2), nullable=True),
        sa.Column("change_due", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "stock_moves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", stock_move_reason, nullable=False),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_stock_moves_product_id", "stock_moves", ["product_id"])
    op.create_index("ix_stock_moves_bill_id", "stock_moves", ["bill_id"])
    op.create_index("ix_stock_moves_created_at", "stock_moves", ["created_at"])


def downgrade() -> None:
    op.drop_table("stock_moves")
    op.drop_table("payments")
    op.drop_table("bill_lines")
    op.drop_table("bills")
    op.execute("DROP SEQUENCE IF EXISTS bill_no_seq")
    op.drop_table("products")
    op.drop_table("users")
    sa.Enum(name="payment_method").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stock_move_reason").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
