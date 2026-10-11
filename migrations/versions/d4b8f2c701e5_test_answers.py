from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4b8f2c701e5'
down_revision: Union[str, Sequence[str], None] = 'c7e3f5a91b26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'test_answers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('test_sessions.id'), nullable=False, index=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False, index=True),
        sa.Column('option_index', sa.Integer(), nullable=True),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('annotation', sa.JSON(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('test_answers')
