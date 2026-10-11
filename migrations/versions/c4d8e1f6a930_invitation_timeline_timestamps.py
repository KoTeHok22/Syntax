from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d8e1f6a930"
down_revision: Union[str, Sequence[str], None] = "a7c1e9d4b820"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invitations", sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("invitations", "responded_at")
    op.drop_column("invitations", "viewed_at")
