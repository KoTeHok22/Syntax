from alembic import op
import sqlalchemy as sa

revision = "a7b2c9d4e610"
down_revision = "f6a1b3c4d508"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("interview_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("interview_duration", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("interview_format", sa.String(length=16), nullable=True))
    op.add_column("applications", sa.Column("interview_link", sa.String(length=512), nullable=True))
    op.add_column("applications", sa.Column("interview_address", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("applications", "interview_address")
    op.drop_column("applications", "interview_link")
    op.drop_column("applications", "interview_format")
    op.drop_column("applications", "interview_duration")
    op.drop_column("applications", "interview_at")
