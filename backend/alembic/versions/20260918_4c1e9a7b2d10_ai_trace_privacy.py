"""AI traces record whether identifiers were pseudonymised before the LLM call

Revision ID: 4c1e9a7b2d10
Revises: 755f39ee55d1
Create Date: 2026-09-18 18:10:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4c1e9a7b2d10"
down_revision: Union[str, Sequence[str], None] = "755f39ee55d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_query_traces", sa.Column("privacy", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_query_traces", "privacy")
