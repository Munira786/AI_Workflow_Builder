"""Token usage per run, token revocation, pagination indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )
    with op.batch_alter_table("runs") as batch:
        batch.add_column(
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0")
        )
    op.create_index("ix_runs_owner_created", "runs", ["owner_id", "created_at", "id"])
    op.create_index(
        "ix_pipelines_owner_updated", "pipelines", ["owner_id", "updated_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_pipelines_owner_updated", table_name="pipelines")
    op.drop_index("ix_runs_owner_created", table_name="runs")
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("output_tokens")
        batch.drop_column("input_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
