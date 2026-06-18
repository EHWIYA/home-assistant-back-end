"""schedule recurrence and holiday fields

Revision ID: 003_schedule_recurrence
Revises: 002_schedules
Create Date: 2026-06-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_schedule_recurrence"
down_revision: Union[str, None] = "002_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schedules",
        sa.Column("recurrence_type", sa.String(length=16), nullable=False, server_default="weekly"),
    )
    op.add_column(
        "schedules",
        sa.Column(
            "specific_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "schedules",
        sa.Column(
            "exclude_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "schedules",
        sa.Column("holiday_mode", sa.String(length=16), nullable=False, server_default="ignore"),
    )
    op.add_column(
        "schedules",
        sa.Column("include_substitute", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("schedules", "include_substitute")
    op.drop_column("schedules", "holiday_mode")
    op.drop_column("schedules", "exclude_dates")
    op.drop_column("schedules", "specific_dates")
    op.drop_column("schedules", "recurrence_type")
