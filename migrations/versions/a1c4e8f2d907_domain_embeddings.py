from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c4e8f2d907'
down_revision: Union[str, Sequence[str], None] = '3f8c1d6a0e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE domains ADD COLUMN embedding vector(1024)")
    with op.batch_alter_table('domains', schema=None) as batch_op:
        batch_op.add_column(sa.Column('embedding_text', sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('domains', schema=None) as batch_op:
        batch_op.drop_column('embedding_text')
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE domains DROP COLUMN IF EXISTS embedding")
