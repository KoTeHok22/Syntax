from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7c3e9a1f2b40'
down_revision: Union[str, Sequence[str], None] = '1b60da01b43c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('employer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('logo_data_url', sa.Text(), nullable=True))

    op.create_table('company_offices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employer_profile_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=128), nullable=False),
    sa.Column('city', sa.String(length=128), nullable=False),
    sa.Column('address', sa.String(length=512), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('company_offices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_company_offices_employer_profile_id'), ['employer_profile_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('company_offices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_company_offices_employer_profile_id'))
    op.drop_table('company_offices')
    with op.batch_alter_table('employer_profiles', schema=None) as batch_op:
        batch_op.drop_column('logo_data_url')
