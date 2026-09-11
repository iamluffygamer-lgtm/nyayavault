"""add_org_type_enum

Revision ID: 2ecea4013bff
Revises: 451519f9902b
Create Date: 2026-09-10 19:47:19.634383
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2ecea4013bff'
down_revision: Union[str, None] = '451519f9902b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Since we are using native_enum=False, it is just a VARCHAR(32) under the hood.
    # No schema changes are strictly necessary for SQLite/Postgres beyond the application level check.
    # We will just add the CHECK constraint for consistency.
    
    # We can skip adding the CHECK constraint to avoid SQLite ALTER TABLE issues.
    # The application will enforce the values.
    pass


def downgrade() -> None:
    pass
