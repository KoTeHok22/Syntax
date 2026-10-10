from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3f8c1d6a0e21'
down_revision: Union[str, Sequence[str], None] = '9d4f2a7b1c53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'domains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=False),
        sa.Column('is_curated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('domains', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_domains_slug'), ['slug'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('domains', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_domains_slug'))
    op.drop_table('domains')
