"""Store the optional Bark destination encrypted; existing installs remain disabled."""

import sqlalchemy as sa
from alembic import op

revision = "20261028_000000_add_bark_notification_secret"
down_revision = "20260918_000000_merge_scim_and_overflow_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("dashboard_settings")}
    if "bark_url_encrypted" not in columns:
        op.add_column("dashboard_settings", sa.Column("bark_url_encrypted", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("dashboard_settings")}
    if "bark_url_encrypted" in columns:
        op.drop_column("dashboard_settings", "bark_url_encrypted")
