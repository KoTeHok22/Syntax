from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9d4f2a7b1c53'
down_revision: Union[str, Sequence[str], None] = '7c3e9a1f2b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('employer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('logo_zoom', sa.Float(), nullable=False, server_default='1.0'))
        batch_op.add_column(sa.Column('logo_offset_x', sa.Float(), nullable=False, server_default='0.0'))
        batch_op.add_column(sa.Column('logo_offset_y', sa.Float(), nullable=False, server_default='0.0'))


def downgrade() -> None:
    with op.batch_alter_table('employer_profiles', schema=None) as batch_op:
        batch_op.drop_column('logo_offset_y')
        batch_op.drop_column('logo_offset_x')
        batch_op.drop_column('logo_zoom')
