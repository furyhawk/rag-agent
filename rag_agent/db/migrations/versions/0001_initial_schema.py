"""Initial schema for tracked documents and sync logs.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("ingested", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sync_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tracked_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("filesize", sa.Integer(), nullable=False),
        sa.Column("filetype", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("vector_document_id", sa.String(length=255), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_tracked_documents_collection_status",
        "tracked_documents",
        ["collection_name", "status"],
        unique=False,
    )
    op.create_index(
        "ix_tracked_documents_content_hash",
        "tracked_documents",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_tracked_documents_source_path",
        "tracked_documents",
        ["source_path"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tracked_documents_source_path", table_name="tracked_documents")
    op.drop_index("ix_tracked_documents_content_hash", table_name="tracked_documents")
    op.drop_index(
        "ix_tracked_documents_collection_status", table_name="tracked_documents"
    )
    op.drop_table("tracked_documents")
    op.drop_table("sync_logs")
