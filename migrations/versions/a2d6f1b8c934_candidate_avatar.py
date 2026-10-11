from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2d6f1b8c934'
down_revision: Union[str, Sequence[str], None] = 'f6a1b3c4d508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avatar_data_url', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('avatar_zoom', sa.Float(), nullable=False, server_default='1.0'))
        batch_op.add_column(sa.Column('avatar_offset_x', sa.Float(), nullable=False, server_default='0.0'))
        batch_op.add_column(sa.Column('avatar_offset_y', sa.Float(), nullable=False, server_default='0.0'))


def downgrade() -> None:
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_column('avatar_offset_y')
        batch_op.drop_column('avatar_offset_x')
        batch_op.drop_column('avatar_zoom')
        batch_op.drop_column('avatar_data_url')
