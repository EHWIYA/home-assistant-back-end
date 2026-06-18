"""widen control_audit.source for schedule:<uuid>

Revision ID: 004_control_audit_source
Revises: 003_schedule_recurrence
Create Date: 2026-06-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_control_audit_source"
down_revision: Union[str, None] = "003_schedule_recurrence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "control_audit",
        "source",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "control_audit",
        "source",
        existing_type=sa.String(length=128),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
