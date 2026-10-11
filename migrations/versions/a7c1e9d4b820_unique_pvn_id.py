from typing import Sequence, Union

from alembic import op

revision: str = "a7c1e9d4b820"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_pvn_id")
        batch.create_unique_constraint("uq_users_pvn_id", ["pvn_id"])
        batch.create_index("ix_users_pvn_id", ["pvn_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_pvn_id")
        batch.drop_constraint("uq_users_pvn_id", type_="unique")
        batch.create_index("ix_users_pvn_id", ["pvn_id"])
