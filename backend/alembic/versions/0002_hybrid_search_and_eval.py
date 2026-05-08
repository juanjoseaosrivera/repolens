"""Add AST metadata, tsvector search, pg_trgm indexes, and eval_runs table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Phase 2 columns on chunks ---
    op.add_column("chunks", sa.Column("symbols_defined", sa.JSON(), nullable=True))
    op.add_column("chunks", sa.Column("imports", sa.JSON(), nullable=True))

    # tsvector column via raw SQL (SA doesn't have a native tsvector type)
    op.execute("ALTER TABLE chunks ADD COLUMN search_vector tsvector")

    # Populate search_vector from content for existing rows
    op.execute(
        "UPDATE chunks SET search_vector = to_tsvector('english', content) "
        "WHERE search_vector IS NULL"
    )

    # Trigger to auto-populate search_vector on INSERT/UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION chunks_search_vector_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', NEW.content);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_chunks_search_vector
            BEFORE INSERT OR UPDATE OF content ON chunks
            FOR EACH ROW
            EXECUTE FUNCTION chunks_search_vector_trigger()
    """)

    # GIN index on tsvector for full-text search
    op.execute(
        "CREATE INDEX ix_chunks_search_vector "
        "ON chunks USING gin (search_vector)"
    )

    # pg_trgm index on content for fuzzy/substring search
    op.execute(
        "CREATE INDEX ix_chunks_content_trgm "
        "ON chunks USING gin (content gin_trgm_ops)"
    )

    # GIN indexes on JSONB metadata for containment queries
    op.execute(
        "CREATE INDEX ix_chunks_symbols_defined "
        "ON chunks USING gin (symbols_defined)"
    )
    op.execute(
        "CREATE INDEX ix_chunks_imports "
        "ON chunks USING gin (imports)"
    )

    # --- eval_runs table ---
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")

    op.execute("DROP TRIGGER IF EXISTS trg_chunks_search_vector ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_search_vector_trigger()")
    op.execute("DROP INDEX IF EXISTS ix_chunks_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_chunks_symbols_defined")
    op.execute("DROP INDEX IF EXISTS ix_chunks_imports")

    op.drop_column("chunks", "search_vector")
    op.drop_column("chunks", "imports")
    op.drop_column("chunks", "symbols_defined")
