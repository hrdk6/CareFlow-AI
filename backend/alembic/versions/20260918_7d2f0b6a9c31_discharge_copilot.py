"""Discharge co-pilot: AI drafts awaiting sign-off, and provenance on signed records

Revision ID: 7d2f0b6a9c31
Revises: 4c1e9a7b2d10
Create Date: 2026-09-18 19:40:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7d2f0b6a9c31"
down_revision: Union[str, Sequence[str], None] = "4c1e9a7b2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("medical_records", sa.Column("ai_provenance", sa.JSON(), nullable=True))
    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Enum("discharge_summary", name="ai_draft_kind", native_enum=False,
                                  create_constraint=True, length=32), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("admission_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", sa.Enum("draft", "signed", "superseded", name="ai_draft_status", native_enum=False,
                                    create_constraint=True, length=32), nullable=False),
        sa.Column("generated_by", sa.String(length=128), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("signed_record_id", sa.Integer(), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admission_id"], ["admissions.id"], name=op.f("fk_ai_drafts_admission_id_admissions"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"],
                                name=op.f("fk_ai_drafts_created_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], name=op.f("fk_ai_drafts_patient_id_patients"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signed_record_id"], ["medical_records.id"],
                                name=op.f("fk_ai_drafts_signed_record_id_medical_records"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_drafts")),
    )
    op.create_index(op.f("ix_ai_drafts_patient_id"), "ai_drafts", ["patient_id"], unique=False)
    op.create_index("ix_ai_drafts_admission_status", "ai_drafts", ["admission_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_drafts_admission_status", table_name="ai_drafts")
    op.drop_index(op.f("ix_ai_drafts_patient_id"), table_name="ai_drafts")
    op.drop_table("ai_drafts")
    op.drop_column("medical_records", "ai_provenance")
