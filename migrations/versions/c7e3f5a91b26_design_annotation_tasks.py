from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c7e3f5a91b26'
down_revision: Union[str, Sequence[str], None] = 'a2d6f1b8c934'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_data_url', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('flaw_hint', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('flaw_hint')
        batch_op.drop_column('image_data_url')
