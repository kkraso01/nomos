"""enable unaccent + search gin index

Revision ID: a0767aa5ba0f
Revises: 4a7c5fe46504
Create Date: 2026-09-23 18:17:52.593085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0767aa5ba0f'
down_revision: Union[str, Sequence[str], None] = '4a7c5fe46504'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    conn = op.get_bind()
    if not conn.dialect.name == "postgresql":
        return
    op.execute("""
        CREATE OR REPLACE FUNCTION public.f_unaccent(text)
        RETURNS text AS
        $func$
        SELECT public.unaccent('public.unaccent', $1)
        $func$
        LANGUAGE sql IMMUTABLE PARALLEL SAFE
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_search_entries_body_tsv
        ON search_entries USING gin (to_tsvector('simple', public.f_unaccent(body)))
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_search_entries_body_tsv")
    op.execute("DROP FUNCTION IF EXISTS public.f_unaccent(text)")
